from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import datetime, timezone

from .models import Edge, Entity, Evidence, Finding, PublicPost, new_id
from .store import Store


def _normalize(text: str) -> str:
    text = re.sub(r"https?://\S+", " URL ", text.casefold())
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_time(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def analyze_public_posts(store: Store, case_id: str, posts: list[PublicPost]) -> dict:
    evidence_added = findings_added = entities_added = 0
    groups: dict[str, list[tuple[PublicPost, Evidence, Entity, datetime | None]]] = defaultdict(list)

    for post in posts:
        normalized = _normalize(post.text)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        raw_digest = hashlib.sha256(post.model_dump_json().encode("utf-8")).hexdigest()

        evidence = Evidence(
            id=new_id("ev"),
            case_id=case_id,
            source=post.platform,
            collector="public-post-import",
            source_url=post.url,
            excerpt=post.text[:500],
            metadata={
                "author_handle": post.author_handle,
                "published_at": post.published_at,
                "normalized_text_hash": digest,
            },
            reliability=0.65,
            content_hash=raw_digest,
            observed_at=post.published_at,
        )
        store.add_evidence(evidence)
        evidence_added += 1

        account = Entity(
            id=new_id("ent"),
            case_id=case_id,
            kind="account",
            label=f"@{post.author_handle} · {post.platform}",
            canonical_key=f"account:{post.platform.casefold()}:{post.author_handle.casefold()}",
            properties={"platform": post.platform, "handle": post.author_handle},
            confidence=0.72,
        )
        account, created = store.upsert_entity(account)
        entities_added += int(created)
        groups[digest].append((post, evidence, account, _parse_time(post.published_at)))

    for digest, rows in groups.items():
        authors = {r[0].author_handle.casefold() for r in rows}
        if len(authors) < 3:
            continue

        times = sorted(r[3] for r in rows if r[3] is not None)
        if len(times) < 3:
            continue

        spread_minutes = (times[-1] - times[0]).total_seconds() / 60
        if spread_minutes > 30:
            continue

        narrative = Entity(
            id=new_id("ent"),
            case_id=case_id,
            kind="content_cluster",
            label=f"shared content · {digest[:8]}",
            canonical_key=f"content:{digest}",
            properties={
                "authors": sorted(authors),
                "post_count": len(rows),
                "spread_minutes": round(spread_minutes, 1),
            },
            confidence=min(0.92, 0.58 + 0.05 * len(authors)),
        )
        narrative, created = store.upsert_entity(narrative)
        entities_added += int(created)

        evidence_ids: list[str] = []
        for _, ev, account, _ in rows:
            evidence_ids.append(ev.id)
            store.add_edge(
                Edge(
                    id=new_id("edge"),
                    case_id=case_id,
                    source_id=account.id,
                    target_id=narrative.id,
                    relation="published_same_content",
                    confidence=0.72,
                    rationale=[
                        "texto público normalizado idêntico",
                        f"publicação dentro de janela de {round(spread_minutes, 1)} minutos",
                    ],
                    evidence_ids=[ev.id],
                )
            )

        confidence = min(0.94, 0.62 + 0.04 * len(authors))
        store.add_finding(
            Finding(
                id=new_id("finding"),
                case_id=case_id,
                category="coordinated-behavior",
                severity="medium",
                title="Cluster de conteúdo sincronizado",
                summary=(
                    f"{len(authors)} contas publicaram conteúdo normalizado idêntico "
                    f"em aproximadamente {round(spread_minutes, 1)} minutos. "
                    "Isto é um indicador de coordenação, não prova de autoria comum ou operação de influência."
                ),
                confidence=confidence,
                evidence_ids=evidence_ids,
            )
        )
        findings_added += 1

    return {
        "entities_added": entities_added,
        "evidence_added": evidence_added,
        "findings_added": findings_added,
    }
