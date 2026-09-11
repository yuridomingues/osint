from __future__ import annotations

from difflib import SequenceMatcher
from urllib.parse import urlparse

from .models import Assessment, ImpersonationSignals


def text_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    left = "".join(c for c in a.casefold() if c.isalnum())
    right = "".join(c for c in b.casefold() if c.isalnum())
    return SequenceMatcher(None, left, right).ratio() if left and right else 0.0


def hostname(value: str) -> str:
    try:
        parsed = urlparse(value if "://" in value else f"https://{value}")
        return (parsed.hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def correlation_score(
    handle_similarity: float,
    display_name_similarity: float,
    shared_external_domain: bool,
    shared_media_hash: bool,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    if handle_similarity >= 0.98:
        score += 0.30; reasons.append("handle praticamente idêntico")
    elif handle_similarity >= 0.82:
        score += 0.18; reasons.append("handle fortemente similar")
    if display_name_similarity >= 0.92:
        score += 0.12; reasons.append("display name muito similar")
    if shared_external_domain:
        score += 0.28; reasons.append("domínio externo compartilhado")
    if shared_media_hash:
        score += 0.30; reasons.append("mídia pública reutilizada")
    return round(min(score, 0.99), 3), reasons


def assess_impersonation(s: ImpersonationSignals) -> Assessment:
    score = 0.0
    reasons: list[str] = []
    if s.handle_similarity >= 0.90:
        score += 0.22; reasons.append("handle muito parecido com a referência")
    elif s.handle_similarity >= 0.75:
        score += 0.12; reasons.append("handle parecido com a referência")
    if s.display_name_similarity >= 0.90:
        score += 0.12; reasons.append("nome de exibição praticamente idêntico")
    if s.reused_visual_identity:
        score += 0.24; reasons.append("identidade visual reutilizada")
    if s.official_link_reuse:
        score += 0.10; reasons.append("links oficiais reutilizados")
    if s.suspicious_external_domain:
        score += 0.20; reasons.append("domínio externo divergente/suspeito")
    if s.sparse_profile:
        score += 0.05; reasons.append("perfil com histórico escasso")
    if s.synchronized_activity:
        score += 0.10; reasons.append("atividade sincronizada com outros perfis")
    score = round(min(score, 1.0), 3)
    level = "low" if score < 0.35 else "medium" if score < 0.65 else "high"
    return Assessment(score=score, level=level, reasons=reasons)
