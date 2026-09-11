from __future__ import annotations

import csv
import io
import json
from typing import Any

from .correlation import import_public_observations
from .models import PublicObservation
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
            for key in ("results", "accounts", "sites"):
                value = parsed.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]
                if isinstance(value, dict):
                    return [
                        {"site_name": name, **row}
                        for name, row in value.items()
                        if isinstance(row, dict)
                    ]
            return [
                {"site_name": name, **row}
                for name, row in parsed.items()
                if isinstance(row, dict)
            ]
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
    for row in _json_records(content):
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


def import_tool_export(store: Store, case_id: str, tool: str, content: str) -> dict:
    if tool == "sherlock_csv":
        observations = _sherlock_csv(content)
    elif tool == "maigret_json":
        observations = _maigret_json(content)
    else:
        raise ValueError("Unsupported tool import")

    entities, evidence = import_public_observations(store, case_id, observations)
    return {
        "tool": tool,
        "records_parsed": len(observations),
        "entities_added": entities,
        "evidence_added": evidence,
    }
