from __future__ import annotations

import ipaddress
from urllib.parse import quote, urlparse

import httpx

from .models import Edge, Entity, Evidence, Finding, new_id
from .store import Store


async def collect_ip_public_sources(
    store: Store,
    case_id: str,
    target: str,
) -> tuple[int, int, int, list[str]]:
    warnings: list[str] = []
    created = evidence_added = findings_added = 0

    try:
        ip = ipaddress.ip_address(target.strip())
    except ValueError:
        return 0, 0, 0, ["Alvo IP inválido."]

    root = Entity(
        id=new_id("ent"),
        case_id=case_id,
        kind="ip",
        label=str(ip),
        canonical_key=f"ip:{ip}",
        properties={"version": ip.version, "is_global": ip.is_global},
        confidence=0.98,
    )
    root, was_created = store.upsert_entity(root)
    created += int(was_created)

    if not ip.is_global:
        return created, 0, 0, ["O IP não é global; VIGIL não consulta redes privadas/reservadas."]

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(12.0),
        headers={"User-Agent": "VIGIL-OSINT/0.2 public-source-research"},
        follow_redirects=True,
    ) as client:
        try:
            response = await client.get(f"https://rdap.org/ip/{quote(str(ip))}")
            response.raise_for_status()
            data = response.json()
            network = data.get("name") or data.get("handle") or "RDAP network"
            country = data.get("country")
            start = data.get("startAddress")
            end = data.get("endAddress")

            ev = Evidence(
                id=new_id("ev"),
                case_id=case_id,
                source="RDAP",
                collector="rdap.org",
                source_url=f"https://rdap.org/ip/{ip}",
                excerpt=f"Public allocation record: {network}",
                metadata={
                    "network": network,
                    "country": country,
                    "start_address": start,
                    "end_address": end,
                    "type": data.get("type"),
                },
                reliability=0.9,
            )
            store.add_evidence(ev)
            evidence_added += 1

            allocation = Entity(
                id=new_id("ent"),
                case_id=case_id,
                kind="network_allocation",
                label=str(network),
                canonical_key=f"allocation:{start}:{end}",
                properties={"country": country, "start": start, "end": end},
                confidence=0.9,
            )
            allocation, was_created = store.upsert_entity(allocation)
            created += int(was_created)
            store.add_edge(
                Edge(
                    id=new_id("edge"),
                    case_id=case_id,
                    source_id=root.id,
                    target_id=allocation.id,
                    relation="allocated_within",
                    confidence=0.92,
                    rationale=["network allocation observed in public RDAP"],
                    evidence_ids=[ev.id],
                )
            )
        except Exception as exc:
            warnings.append(f"IP RDAP indisponível: {type(exc).__name__}")

    if evidence_added:
        finding = Finding(
            id=new_id("finding"),
            case_id=case_id,
            category="infrastructure",
            severity="info",
            title="IP allocation context collected",
            summary="Public network-allocation context was added. This describes infrastructure ownership/allocation, not a person's physical location.",
            confidence=0.9,
        )
        store.add_finding(finding)
        findings_added += 1

    return created, evidence_added, findings_added, warnings


async def collect_url_public_sources(
    store: Store,
    case_id: str,
    target: str,
) -> tuple[int, int, int, list[str]]:
    warnings: list[str] = []
    created = evidence_added = findings_added = 0

    parsed = urlparse(target.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return 0, 0, 0, ["Alvo URL inválido; use http:// ou https://."]

    normalized = parsed.geturl()
    host = parsed.hostname.lower().removeprefix("www.")

    url_entity = Entity(
        id=new_id("ent"),
        case_id=case_id,
        kind="url",
        label=normalized,
        canonical_key=f"url:{normalized}",
        properties={"host": host, "path": parsed.path},
        confidence=0.98,
    )
    url_entity, was_created = store.upsert_entity(url_entity)
    created += int(was_created)

    domain = Entity(
        id=new_id("ent"),
        case_id=case_id,
        kind="domain",
        label=host,
        canonical_key=f"domain:{host}",
        properties={},
        confidence=0.9,
    )
    domain, was_created = store.upsert_entity(domain)
    created += int(was_created)

    store.add_edge(
        Edge(
            id=new_id("edge"),
            case_id=case_id,
            source_id=url_entity.id,
            target_id=domain.id,
            relation="hosted_on_domain",
            confidence=0.98,
            rationale=["hostname parsed directly from supplied public URL"],
            evidence_ids=[],
        )
    )

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(12.0),
        headers={"User-Agent": "VIGIL-OSINT/0.2 public-source-research"},
        follow_redirects=True,
    ) as client:
        try:
            response = await client.get(
                "https://web.archive.org/cdx/search/cdx",
                params={
                    "url": normalized,
                    "output": "json",
                    "fl": "timestamp,original,statuscode,digest",
                    "filter": "statuscode:200",
                    "limit": "25",
                },
            )
            response.raise_for_status()
            rows = response.json()
            captures = rows[1:] if rows and isinstance(rows[0], list) else rows
            ev = Evidence(
                id=new_id("ev"),
                case_id=case_id,
                source="Internet Archive",
                collector="wayback-cdx",
                source_url=f"https://web.archive.org/web/*/{normalized}",
                excerpt=f"{len(captures)} public archive captures found for the URL",
                metadata={"captures": captures[:25]},
                reliability=0.82,
            )
            store.add_evidence(ev)
            evidence_added += 1
            if captures:
                store.add_edge(
                    Edge(
                        id=new_id("edge"),
                        case_id=case_id,
                        source_id=url_entity.id,
                        target_id=domain.id,
                        relation="archived_under",
                        confidence=0.82,
                        rationale=["URL observed in public Internet Archive index"],
                        evidence_ids=[ev.id],
                    )
                )
        except Exception as exc:
            warnings.append(f"Internet Archive indisponível: {type(exc).__name__}")

    return created, evidence_added, findings_added, warnings
