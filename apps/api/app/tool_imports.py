from __future__ import annotations

import csv
import hashlib
import io
import json
from typing import Any

from .correlation import import_public_observations
from .models import Edge, Entity, Evidence, PublicObservation, TargetType, new_id
from .store import Store


def _claimed(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().casefold()
    return text in {"true", "yes", "1", "claimed", "found"} or "claimed" in text


def _sherlock_csv(content: str) -> list[PublicObservation]:
    observations: list[PublicObservation] = []
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        if not _claimed(row.get("exists")):
            continue
        username = (row.get("username") or "").strip()
        platform = (row.get("name") or "unknown").strip()
        url = (row.get("url_user") or "").strip() or None
        if username and platform:
            observations.append(
                PublicObservation(
                    platform=platform,
                    handle=username,
                    profile_url=url,
                )
            )
    return observations


def _json_records(content: str) -> list[dict[str, Any]]:
    stripped = content.strip()
    if not stripped:
        return []

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
        if isinstance(parsed, dict):
            for key in ("results", "accounts", "sites", "data"):
                value = parsed.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]
                if isinstance(value, dict):
                    return [
                        {"site_name": name, **row}
                        for name, row in value.items()
                        if isinstance(row, dict)
                    ]
            return [parsed]
    except json.JSONDecodeError:
        pass

    records: list[dict[str, Any]] = []
    for line in stripped.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def _maigret_json(content: str) -> list[PublicObservation]:
    observations: list[PublicObservation] = []
    records = _json_records(content)

    # Maigret can also emit a top-level object keyed by site.
    if len(records) == 1:
        record = records[0]
        if not any(key in record for key in ("username", "url_user", "status", "site_name")):
            records = [
                {"site_name": name, **row}
                for name, row in record.items()
                if isinstance(row, dict)
            ]

    for row in records:
        status = row.get("status")
        if isinstance(status, dict):
            status = status.get("status") or status.get("value")
        if status is not None and not _claimed(status):
            continue

        username = str(
            row.get("username")
            or row.get("id")
            or row.get("searched_username")
            or ""
        ).strip()
        platform = str(
            row.get("site_name")
            or row.get("site")
            or row.get("name")
            or "unknown"
        ).strip()
        url = str(
            row.get("url_user")
            or row.get("url")
            or row.get("profile_url")
            or ""
        ).strip() or None

        if not username and url:
            username = url.rstrip("/").rsplit("/", 1)[-1]

        if username and platform:
            observations.append(
                PublicObservation(
                    platform=platform,
                    handle=username,
                    profile_url=url,
                    display_name=row.get("fullname") or row.get("display_name"),
                    bio=row.get("bio") or row.get("description"),
                    external_urls=[
                        str(x) for x in (row.get("ids_links") or []) if isinstance(x, str)
                    ],
                )
            )
    return observations


def _root_entity(store: Store, case_id: str) -> Entity:
    case = store.get_case(case_id)
    if not case:
        raise ValueError("Case not found")
    kind = "organization" if case.target_type == TargetType.ORGANIZATION else "domain"
    entity = Entity(
        id=new_id("ent"),
        case_id=case_id,
        kind=kind,
        label=case.target,
        canonical_key=f"{kind}:{case.target.casefold()}",
        properties={"case_root": True},
        confidence=0.98,
    )
    entity, _ = store.upsert_entity(entity)
    return entity


def _add_infra_observation(
    store: Store,
    case_id: str,
    root: Entity,
    *,
    tool: str,
    kind: str,
    value: str,
    metadata: dict[str, Any],
    source_label: str,
) -> tuple[Entity, bool, Evidence]:
    normalized = value.strip().lower() if kind in {"domain", "hostname", "ip"} else value.strip()
    entity = Entity(
        id=new_id("ent"),
        case_id=case_id,
        kind=kind,
        label=normalized,
        canonical_key=f"{kind}:{normalized}",
        properties=metadata,
        confidence=0.78,
    )
    entity, created = store.upsert_entity(entity)

    canonical = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    evidence = Evidence(
        id=new_id("ev"),
        case_id=case_id,
        source=source_label,
        collector=tool,
        excerpt=f"{kind}: {normalized}",
        metadata=metadata,
        reliability=0.72,
        content_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )
    store.add_evidence(evidence)

    store.add_edge(
        Edge(
            id=new_id("edge"),
            case_id=case_id,
            source_id=root.id,
            target_id=entity.id,
            relation="observed_by_tool",
            confidence=0.76,
            rationale=[f"machine-readable {tool} export imported into VIGIL"],
            evidence_ids=[evidence.id],
        )
    )
    return entity, created, evidence


def _import_subfinder(store: Store, case_id: str, content: str) -> dict:
    root = _root_entity(store, case_id)
    created = evidence_added = 0
    records = _json_records(content)

    for row in records:
        host = str(row.get("host") or row.get("name") or "").strip()
        if not host:
            continue
        _, was_created, _ = _add_infra_observation(
            store,
            case_id,
            root,
            tool="subfinder_jsonl",
            kind="hostname",
            value=host,
            metadata={
                "source": row.get("source"),
                "input": row.get("input"),
            },
            source_label="Subfinder",
        )
        created += int(was_created)
        evidence_added += 1

    return {
        "tool": "subfinder_jsonl",
        "records_parsed": len(records),
        "entities_added": created,
        "evidence_added": evidence_added,
    }


def _import_amass(store: Store, case_id: str, content: str) -> dict:
    root = _root_entity(store, case_id)
    created = evidence_added = 0
    records = _json_records(content)

    for row in records:
        name = str(row.get("name") or row.get("hostname") or "").strip()
        if not name:
            continue
        host_entity, was_created, host_ev = _add_infra_observation(
            store,
            case_id,
            root,
            tool="amass_json",
            kind="hostname",
            value=name,
            metadata={
                "domain": row.get("domain"),
                "tag": row.get("tag"),
                "sources": row.get("sources") or [],
            },
            source_label="OWASP Amass",
        )
        created += int(was_created)
        evidence_added += 1

        addresses = row.get("addresses") or []
        if isinstance(addresses, list):
            for address in addresses:
                if not isinstance(address, dict):
                    continue
                ip = str(address.get("ip") or "").strip()
                if not ip:
                    continue
                ip_entity, ip_created, ip_ev = _add_infra_observation(
                    store,
                    case_id,
                    root,
                    tool="amass_json",
                    kind="ip",
                    value=ip,
                    metadata={
                        "cidr": address.get("cidr"),
                        "asn": address.get("asn"),
                        "desc": address.get("desc"),
                    },
                    source_label="OWASP Amass",
                )
                created += int(ip_created)
                evidence_added += 1
                store.add_edge(
                    Edge(
                        id=new_id("edge"),
                        case_id=case_id,
                        source_id=host_entity.id,
                        target_id=ip_entity.id,
                        relation="resolves_to",
                        confidence=0.76,
                        rationale=["hostname/IP relationship imported from Amass output"],
                        evidence_ids=[host_ev.id, ip_ev.id],
                    )
                )

    return {
        "tool": "amass_json",
        "records_parsed": len(records),
        "entities_added": created,
        "evidence_added": evidence_added,
    }


def _spiderfoot_kind(type_value: str, data: str) -> str | None:
    value = type_value.casefold()
    if "ip" in value and "address" in value:
        return "ip"
    if "url" in value:
        return "url"
    if any(token in value for token in ("internet name", "hostname", "domain")):
        return "hostname"
    # Deliberately skip person/contact selectors from broad SpiderFoot exports.
    return None


def _import_spiderfoot(store: Store, case_id: str, content: str) -> dict:
    root = _root_entity(store, case_id)
    created = evidence_added = parsed = 0
    reader = csv.DictReader(io.StringIO(content))

    for row in reader:
        type_value = str(row.get("Type") or row.get("type") or "")
        data = str(row.get("Data") or row.get("data") or "").strip()
        kind = _spiderfoot_kind(type_value, data)
        if not kind or not data:
            continue
        parsed += 1
        _, was_created, _ = _add_infra_observation(
            store,
            case_id,
            root,
            tool="spiderfoot_csv",
            kind=kind,
            value=data,
            metadata={
                "type": type_value,
                "module": row.get("Module") or row.get("module"),
                "source": row.get("Source") or row.get("source"),
            },
            source_label="SpiderFoot",
        )
        created += int(was_created)
        evidence_added += 1

    return {
        "tool": "spiderfoot_csv",
        "records_parsed": parsed,
        "entities_added": created,
        "evidence_added": evidence_added,
    }


def import_tool_export(store: Store, case_id: str, tool: str, content: str) -> dict:
    if tool == "sherlock_csv":
        observations = _sherlock_csv(content)
        entities, evidence = import_public_observations(store, case_id, observations)
        return {
            "tool": tool,
            "records_parsed": len(observations),
            "entities_added": entities,
            "evidence_added": evidence,
        }

    if tool == "maigret_json":
        observations = _maigret_json(content)
        entities, evidence = import_public_observations(store, case_id, observations)
        return {
            "tool": tool,
            "records_parsed": len(observations),
            "entities_added": entities,
            "evidence_added": evidence,
        }

    if tool == "subfinder_jsonl":
        return _import_subfinder(store, case_id, content)
    if tool == "amass_json":
        return _import_amass(store, case_id, content)
    if tool == "spiderfoot_csv":
        return _import_spiderfoot(store, case_id, content)

    raise ValueError("Unsupported tool import")
