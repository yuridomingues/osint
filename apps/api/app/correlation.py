from __future__ import annotations

from itertools import combinations

from .analysis import correlation_score, hostname, text_similarity
from .models import Edge, Entity, Evidence, PublicObservation, new_id
from .store import Store


def import_public_observations(store: Store, case_id: str, observations: list[PublicObservation]) -> tuple[int, int]:
    created = 0
    evidence_count = 0
    accounts: list[tuple[PublicObservation, Entity, Evidence]] = []

    for obs in observations:
        evidence = Evidence(
            id=new_id("ev"),
            case_id=case_id,
            source=obs.platform,
            collector="public-observation-import",
            source_url=obs.profile_url,
            excerpt=(obs.bio or "")[:500],
            metadata={"handle": obs.handle, "display_name": obs.display_name},
            reliability=0.65,
            observed_at=obs.observed_at or Evidence.model_fields["observed_at"].default_factory(),
        )
        store.add_evidence(evidence)
        evidence_count += 1

        account = Entity(
            id=new_id("ent"),
            case_id=case_id,
            kind="account",
            label=f"@{obs.handle} · {obs.platform}",
            canonical_key=f"account:{obs.platform.casefold()}:{obs.handle.casefold()}",
            properties={
                "platform": obs.platform,
                "handle": obs.handle,
                "profile_url": obs.profile_url,
                "display_name": obs.display_name,
                "bio": obs.bio,
                "external_urls": obs.external_urls,
                "media_hashes": obs.media_hashes,
            },
            confidence=0.72,
        )
        account, was_created = store.upsert_entity(account)
        created += int(was_created)
        accounts.append((obs, account, evidence))

        for url in obs.external_urls:
            host = hostname(url)
            if not host:
                continue
            domain = Entity(
                id=new_id("ent"), case_id=case_id, kind="domain", label=host,
                canonical_key=f"domain:{host}", properties={"source_url": url}, confidence=0.78
            )
            domain, was_created = store.upsert_entity(domain)
            created += int(was_created)
            store.add_edge(Edge(
                id=new_id("edge"), case_id=case_id, source_id=account.id, target_id=domain.id,
                relation="links_to", confidence=0.90, rationale=["URL pública declarada no perfil"],
                evidence_ids=[evidence.id]
            ))

    for (left_obs, left_ent, left_ev), (right_obs, right_ent, right_ev) in combinations(accounts, 2):
        left_domains = {hostname(u) for u in left_obs.external_urls if hostname(u)}
        right_domains = {hostname(u) for u in right_obs.external_urls if hostname(u)}
        shared_domain = bool(left_domains & right_domains)
        shared_media = bool(set(left_obs.media_hashes) & set(right_obs.media_hashes))
        score, reasons = correlation_score(
            text_similarity(left_obs.handle, right_obs.handle),
            text_similarity(left_obs.display_name, right_obs.display_name),
            shared_domain,
            shared_media,
        )
        if score >= 0.30 and reasons:
            store.add_edge(Edge(
                id=new_id("edge"), case_id=case_id, source_id=left_ent.id, target_id=right_ent.id,
                relation="possibly_related", confidence=score, rationale=reasons,
                evidence_ids=[left_ev.id, right_ev.id]
            ))
    return created, evidence_count
