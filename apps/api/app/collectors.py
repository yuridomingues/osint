from __future__ import annotations

import re
from urllib.parse import quote

import httpx

from .models import Edge, Entity, Evidence, Finding, new_id
from .store import Store


DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I)


def valid_domain(value: str) -> bool:
    return bool(DOMAIN_RE.fullmatch(value.strip().lower()))


async def collect_domain_public_sources(store: Store, case_id: str, domain: str) -> tuple[int, int, int, list[str]]:
    domain = domain.strip().lower().removeprefix("www.")
    if not valid_domain(domain):
        return 0, 0, 0, ["O alvo não é um domínio válido; coleta pública de infraestrutura foi ignorada."]

    created = evidence_count = findings_count = 0
    warnings: list[str] = []

    root = Entity(
        id=new_id("ent"), case_id=case_id, kind="domain", label=domain,
        canonical_key=f"domain:{domain}", properties={"root": True}, confidence=0.98
    )
    root, was_created = store.upsert_entity(root)
    created += int(was_created)

    timeout = httpx.Timeout(12.0)
    headers = {"User-Agent": "VIGIL-OSINT/0.1 public-source-research"}

    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
        # Certificate Transparency is a public registry and is used only for passive discovery.
        try:
            response = await client.get("https://crt.sh/", params={"q": f"%.{domain}", "output": "json"})
            response.raise_for_status()
            names: set[str] = set()
            for row in response.json()[:1000]:
                for name in str(row.get("name_value", "")).splitlines():
                    host = name.strip().lower().removeprefix("*.")
                    if host == domain or host.endswith(f".{domain}"):
                        names.add(host)
            ev = Evidence(
                id=new_id("ev"), case_id=case_id, source="Certificate Transparency",
                collector="crt.sh", source_url=f"https://crt.sh/?q=%25.{domain}",
                excerpt=f"{len(names)} nomes públicos observados em certificados",
                metadata={"count": len(names)}, reliability=0.85
            )
            store.add_evidence(ev); evidence_count += 1
            for host in sorted(names)[:250]:
                entity = Entity(
                    id=new_id("ent"), case_id=case_id, kind="hostname", label=host,
                    canonical_key=f"hostname:{host}", properties={}, confidence=0.84
                )
                entity, new = store.upsert_entity(entity); created += int(new)
                if entity.id != root.id:
                    store.add_edge(Edge(
                        id=new_id("edge"), case_id=case_id, source_id=root.id, target_id=entity.id,
                        relation="certificate_name", confidence=0.84,
                        rationale=["nome observado em certificado público"],
                        evidence_ids=[ev.id]
                    ))
        except Exception as exc:
            warnings.append(f"Certificate Transparency indisponível: {type(exc).__name__}")

        # RDAP gives registration metadata without probing the target.
        try:
            response = await client.get(f"https://rdap.org/domain/{quote(domain)}")
            response.raise_for_status()
            data = response.json()
            metadata = {
                "handle": data.get("handle"),
                "status": data.get("status", []),
                "nameservers": [n.get("ldhName") for n in data.get("nameservers", []) if n.get("ldhName")],
                "events": data.get("events", [])[:10],
            }
            ev = Evidence(
                id=new_id("ev"), case_id=case_id, source="RDAP",
                collector="rdap.org", source_url=f"https://rdap.org/domain/{domain}",
                excerpt="metadados públicos de registro do domínio", metadata=metadata, reliability=0.9
            )
            store.add_evidence(ev); evidence_count += 1
            for ns in metadata["nameservers"]:
                ns = ns.lower().rstrip(".")
                entity = Entity(
                    id=new_id("ent"), case_id=case_id, kind="nameserver", label=ns,
                    canonical_key=f"nameserver:{ns}", properties={}, confidence=0.88
                )
                entity, new = store.upsert_entity(entity); created += int(new)
                store.add_edge(Edge(
                    id=new_id("edge"), case_id=case_id, source_id=root.id, target_id=entity.id,
                    relation="uses_nameserver", confidence=0.9,
                    rationale=["nameserver listado em RDAP"], evidence_ids=[ev.id]
                ))
        except Exception as exc:
            warnings.append(f"RDAP indisponível: {type(exc).__name__}")

        # Internet Archive timeline; public historical URLs only.
        try:
            response = await client.get(
                "https://web.archive.org/cdx/search/cdx",
                params={
                    "url": f"{domain}/*", "output": "json", "fl": "timestamp,original,statuscode",
                    "filter": "statuscode:200", "collapse": "urlkey", "limit": "50"
                },
            )
            response.raise_for_status()
            rows = response.json()
            captures = rows[1:] if rows and isinstance(rows[0], list) else rows
            ev = Evidence(
                id=new_id("ev"), case_id=case_id, source="Internet Archive",
                collector="wayback-cdx", source_url=f"https://web.archive.org/web/*/{domain}",
                excerpt=f"{len(captures)} URLs históricas públicas amostradas",
                metadata={"captures": captures[:50]}, reliability=0.8
            )
            store.add_evidence(ev); evidence_count += 1
        except Exception as exc:
            warnings.append(f"Internet Archive indisponível: {type(exc).__name__}")

    if evidence_count >= 2:
        finding = Finding(
            id=new_id("finding"), case_id=case_id, category="coverage", severity="info",
            title="Cobertura pública coletada",
            summary="O domínio possui evidências provenientes de fontes públicas independentes. Revise o grafo e a proveniência antes de tirar conclusões.",
            confidence=0.86
        )
        store.add_finding(finding); findings_count += 1

    return created, evidence_count, findings_count, warnings
