from __future__ import annotations

import base64
import html
import os
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx

from .models import Edge, Entity, Evidence, Finding, new_id
from .store import Store


USER_AGENT = "VIGIL-OSINT/0.3 public-source-identity-discovery"
SEARCH_TIMEOUT = httpx.Timeout(12.0)

PLATFORM_HOSTS: dict[str, tuple[str, ...]] = {
    "instagram": ("instagram.com", "www.instagram.com"),
    "x": ("x.com", "www.x.com", "twitter.com", "www.twitter.com"),
    "github": ("github.com", "www.github.com"),
    "linkedin": ("linkedin.com", "www.linkedin.com"),
    "substack": ("substack.com", "www.substack.com"),
    "medium": ("medium.com", "www.medium.com"),
    "mastodon": ("mastodon.social",),
    "bluesky": ("bsky.app",),
    "youtube": ("youtube.com", "www.youtube.com"),
    "tiktok": ("tiktok.com", "www.tiktok.com"),
}

SAFE_PROFILE_HOSTS = {host for hosts in PLATFORM_HOSTS.values() for host in hosts}
CONTACT_RE = re.compile(
    r"(?i)(?:[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|\+?\d[\d\s().-]{7,}\d)"
)
URL_RE = re.compile(r"https?://[^\s<>'\"\\)\]]+")


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str = ""


@dataclass
class Candidate:
    url: str
    platform: str
    handle: str
    title: str = ""
    description: str = ""
    outbound_links: set[str] = field(default_factory=set)
    provenance: str = "web_search"
    evidence_ids: list[str] = field(default_factory=list)


class DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hits: list[SearchHit] = []
        self._in_title = False
        self._in_snippet = False
        self._href = ""
        self._title: list[str] = []
        self._snippet: list[str] = []
        self._pending: SearchHit | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        classes = (data.get("class") or "").split()
        if tag == "a" and "result__a" in classes:
            self._in_title = True
            self._href = data.get("href") or ""
            self._title = []
        if tag in {"a", "div"} and "result__snippet" in classes:
            self._in_snippet = True
            self._snippet = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_title:
            self._in_title = False
            url = _decode_ddg_url(self._href)
            title = _clean_text("".join(self._title))
            if url and title:
                self._pending = SearchHit(title=title, url=url)
                self.hits.append(self._pending)
        if tag in {"a", "div"} and self._in_snippet:
            self._in_snippet = False
            if self._pending:
                self._pending.snippet = _clean_text("".join(self._snippet))
            self._pending = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title.append(data)
        if self._in_snippet:
            self._snippet.append(data)


class PublicPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: list[str] = []
        self._in_title = False
        self.description = ""
        self.og_title = ""
        self.links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            key = (data.get("property") or data.get("name") or "").casefold()
            value = data.get("content") or ""
            if key in {"description", "og:description", "twitter:description"} and not self.description:
                self.description = _clean_text(value)
            if key in {"og:title", "twitter:title"} and not self.og_title:
                self.og_title = _clean_text(value)
        if tag == "a":
            href = data.get("href")
            if href and href.startswith(("http://", "https://")):
                self.links.add(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title.append(data)


def _clean_text(value: str) -> str:
    return " ".join(html.unescape(value or "").split()).strip()


def _redact_contact(value: str) -> str:
    return CONTACT_RE.sub("[contact redacted]", _clean_text(value))


def _decode_ddg_url(value: str) -> str:
    if not value:
        return ""
    value = html.unescape(value)
    if value.startswith("//"):
        value = "https:" + value
    parsed = urlparse(value)
    if "duckduckgo.com" in (parsed.hostname or ""):
        redirected = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(redirected)
    return value


def _normalize_handle(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _platform_for_url(url: str) -> str | None:
    try:
        host = (urlparse(url).hostname or "").casefold()
    except ValueError:
        return None
    for platform, hosts in PLATFORM_HOSTS.items():
        if host in hosts:
            return platform
    return None


def _profile_handle(url: str, platform: str) -> str:
    parsed = urlparse(url)
    parts = [unquote(x) for x in parsed.path.split("/") if x]
    if not parts:
        return ""
    if platform == "substack" and parts[0].startswith("@"):
        return parts[0][1:]
    if platform == "linkedin" and len(parts) >= 2 and parts[0] == "in":
        return parts[1]
    if platform == "github":
        return parts[0]
    if platform == "youtube" and parts[0].startswith("@"):
        return parts[0][1:]
    return parts[0].lstrip("@")


def _canonical_profile(url: str) -> str | None:
    platform = _platform_for_url(url)
    if not platform:
        return None
    parsed = urlparse(url)
    handle = _profile_handle(url, platform)
    if not handle:
        return None

    if platform == "substack":
        return f"https://substack.com/@{handle}"
    if platform == "linkedin":
        return f"https://www.linkedin.com/in/{handle}"
    if platform == "x":
        return f"https://x.com/{handle}"
    if platform == "instagram":
        return f"https://www.instagram.com/{handle}"
    if platform == "github":
        return f"https://github.com/{handle}"
    return f"{parsed.scheme or 'https'}://{parsed.hostname}/{parsed.path.strip('/')}"


def _candidate_name(title: str, handle: str) -> str:
    text = _clean_text(title)
    for suffix in (
        " | LinkedIn",
        " • Instagram",
        " (@",
        " - GitHub",
        " on X",
        " | Substack",
        " - Substack",
    ):
        if suffix in text:
            text = text.split(suffix, 1)[0]
    text = text.strip(" -|•·")
    if not text or _normalize_handle(text) == _normalize_handle(handle):
        return ""
    if 2 <= len(text) <= 100 and not text.lower().startswith(("instagram", "github", "substack")):
        return text
    return ""


def _name_similarity(left: str, right: str) -> float:
    a, b = _clean_text(left).casefold(), _clean_text(right).casefold()
    if not a or not b:
        return 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    ta, tb = set(re.findall(r"[a-zà-ÿ0-9]+", a)), set(re.findall(r"[a-zà-ÿ0-9]+", b))
    jaccard = len(ta & tb) / max(1, len(ta | tb))
    return max(seq, jaccard)


def _safe_outbound(url: str) -> str | None:
    if not url.startswith(("http://", "https://")):
        return None
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    if not host:
        return None
    if host in {"wa.me", "api.whatsapp.com", "whatsapp.com", "www.whatsapp.com"}:
        return None
    return url.split("#", 1)[0]


def score_candidate(
    seed_handle: str,
    names: set[str],
    known_profiles: set[str],
    candidate: Candidate,
) -> tuple[float, list[str], bool]:
    score = 0.0
    reasons: list[str] = []
    strong_signal = False

    if _normalize_handle(candidate.handle) == _normalize_handle(seed_handle):
        score += 0.18
        reasons.append("same normalized username (weak signal)")

    candidate_name = _candidate_name(candidate.title, candidate.handle)
    best_name = max((_name_similarity(candidate_name, name) for name in names), default=0.0)
    if best_name >= 0.90:
        score += 0.30
        reasons.append("display name strongly matches an independently observed public name")
    elif best_name >= 0.72:
        score += 0.18
        reasons.append("display name partially matches an independently observed public name")

    canonical_outbound = {_canonical_profile(url) for url in candidate.outbound_links}
    canonical_outbound.discard(None)
    shared_profiles = {url for url in canonical_outbound if url in known_profiles}
    if shared_profiles:
        score += 0.48
        strong_signal = True
        reasons.append("candidate links back to an already observed public profile")

    if candidate.provenance == "github_history":
        score += 0.60
        strong_signal = True
        reasons.append("profile URL was explicitly present in public Git history")

    if candidate.provenance == "explicit_link":
        score += 0.65
        strong_signal = True
        reasons.append("profile URL was explicitly linked from an observed public profile")

    return min(score, 0.99), reasons, strong_signal


async def _web_search(client: httpx.AsyncClient, query: str) -> tuple[list[SearchHit], str | None]:
    brave_key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    if brave_key:
        try:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 10, "safesearch": "moderate"},
                headers={"Accept": "application/json", "X-Subscription-Token": brave_key},
            )
            response.raise_for_status()
            data = response.json()
            hits = [
                SearchHit(
                    title=_clean_text(item.get("title", "")),
                    url=item.get("url", ""),
                    snippet=_clean_text(item.get("description", "")),
                )
                for item in data.get("web", {}).get("results", [])
                if item.get("url")
            ]
            return hits, None
        except Exception as exc:
            return [], f"Brave Search unavailable: {type(exc).__name__}"

    try:
        response = await client.get("https://html.duckduckgo.com/html/", params={"q": query})
        response.raise_for_status()
        parser = DuckDuckGoParser()
        parser.feed(response.text)
        return parser.hits[:10], None
    except Exception as exc:
        return [], f"DuckDuckGo fallback unavailable: {type(exc).__name__}"


async def _fetch_candidate(client: httpx.AsyncClient, candidate: Candidate) -> Candidate:
    try:
        response = await client.get(candidate.url)
        response.raise_for_status()
        final_host = (response.url.host or "").casefold()
        if final_host not in SAFE_PROFILE_HOSTS:
            return candidate
        parser = PublicPageParser()
        parser.feed(response.text[:1_500_000])
        candidate.title = parser.og_title or _clean_text("".join(parser.title)) or candidate.title
        candidate.description = _redact_contact(parser.description or candidate.description)
        candidate.outbound_links.update(filter(None, (_safe_outbound(x) for x in parser.links)))
    except Exception:
        pass
    return candidate


async def _github_history_links(
    client: httpx.AsyncClient,
    handle: str,
) -> tuple[list[tuple[str, str]], list[str]]:
    warnings: list[str] = []
    results: list[tuple[str, str]] = []
    repo = f"{handle}/{handle}"
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = await client.get(
            f"https://api.github.com/repos/{quote(handle)}/{quote(handle)}/commits",
            params={"per_page": 30},
            headers=headers,
        )
        if response.status_code == 404:
            return [], []
        response.raise_for_status()
        commits = response.json()
    except Exception as exc:
        return [], [f"GitHub history unavailable for {repo}: {type(exc).__name__}"]

    seen: set[str] = set()
    for commit in commits[:20]:
        sha = commit.get("sha")
        if not sha:
            continue
        try:
            raw = await client.get(
                f"https://raw.githubusercontent.com/{quote(handle)}/{quote(handle)}/{sha}/README.md"
            )
            if raw.status_code != 200:
                continue
            for url in URL_RE.findall(raw.text):
                url = html.unescape(url).rstrip(".,;")
                canonical = _canonical_profile(url)
                if canonical and canonical not in seen:
                    seen.add(canonical)
                    results.append((canonical, sha))
        except Exception:
            continue
    return results, warnings


def _seed_from_target(target: str) -> tuple[str, str | None, str | None]:
    value = target.strip()
    if value.startswith(("http://", "https://")):
        platform = _platform_for_url(value)
        if platform:
            return _profile_handle(value, platform), _canonical_profile(value), platform
    return value.lstrip("@"), None, None


async def collect_public_identity_discovery(
    store: Store,
    case_id: str,
    target: str,
) -> tuple[int, int, int, list[str]]:
    seed_handle, seed_url, seed_platform = _seed_from_target(target)
    warnings: list[str] = []
    created = evidence_added = findings_added = 0

    root = Entity(
        id=new_id("ent"),
        case_id=case_id,
        kind="public_account",
        label=f"@{seed_handle}",
        canonical_key=f"public-account:seed:{_normalize_handle(seed_handle)}",
        properties={"handle": seed_handle, "platform": seed_platform or "unknown", "url": seed_url},
        confidence=0.98,
    )
    root, was_created = store.upsert_entity(root)
    created += int(was_created)

    known_profiles: set[str] = set()
    if seed_url:
        known_profiles.add(seed_url)

    names: set[str] = set()
    candidates: dict[str, Candidate] = {}

    async with httpx.AsyncClient(
        timeout=SEARCH_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8"},
        follow_redirects=True,
    ) as client:
        queries = [
            f'"{seed_handle}"',
            f'"{seed_handle}" GitHub',
            f'"{seed_handle}" Substack',
            f'"{seed_handle}" Twitter OR X',
        ]

        for query in queries:
            hits, warning = await _web_search(client, query)
            if warning and warning not in warnings:
                warnings.append(warning)
            for hit in hits:
                platform = _platform_for_url(hit.url)
                canonical = _canonical_profile(hit.url) if platform else None
                if not canonical or not platform:
                    continue
                handle = _profile_handle(canonical, platform)
                if not handle:
                    continue
                candidate = candidates.setdefault(
                    canonical,
                    Candidate(
                        url=canonical,
                        platform=platform,
                        handle=handle,
                        title=hit.title,
                        description=_redact_contact(hit.snippet),
                    ),
                )
                if not candidate.title:
                    candidate.title = hit.title
                possible_name = _candidate_name(hit.title, handle)
                if possible_name:
                    names.add(possible_name)

                ev = Evidence(
                    id=new_id("ev"),
                    case_id=case_id,
                    source="Web search",
                    collector="identity-discovery-search",
                    source_url=canonical,
                    excerpt=_redact_contact(hit.title),
                    metadata={
                        "query": query,
                        "platform": platform,
                        "snippet": _redact_contact(hit.snippet)[:600],
                    },
                    reliability=0.55,
                )
                store.add_evidence(ev)
                candidate.evidence_ids.append(ev.id)
                evidence_added += 1

        # A different handle can still be discoverable through stable public identity anchors.
        # Use names observed in the first pass, not guesses manufactured from the username.
        for name in sorted(names)[:3]:
            for query in (
                f'site:substack.com/@ "{name}"',
                f'"{name}" Substack',
                f'"{name}" GitHub',
                f'"{name}" "x.com"',
            ):
                hits, warning = await _web_search(client, query)
                if warning and warning not in warnings:
                    warnings.append(warning)
                for hit in hits:
                    platform = _platform_for_url(hit.url)
                    canonical = _canonical_profile(hit.url) if platform else None
                    if not canonical or not platform:
                        continue
                    handle = _profile_handle(canonical, platform)
                    if not handle:
                        continue
                    candidate = candidates.setdefault(
                        canonical,
                        Candidate(
                            url=canonical,
                            platform=platform,
                            handle=handle,
                            title=hit.title,
                            description=_redact_contact(hit.snippet),
                        ),
                    )
                    if not candidate.title:
                        candidate.title = hit.title
                    ev = Evidence(
                        id=new_id("ev"),
                        case_id=case_id,
                        source="Web search",
                        collector="identity-discovery-name-pivot",
                        source_url=canonical,
                        excerpt=_redact_contact(hit.title),
                        metadata={"query": query, "platform": platform},
                        reliability=0.55,
                    )
                    store.add_evidence(ev)
                    candidate.evidence_ids.append(ev.id)
                    evidence_added += 1

        # Resolve candidate metadata and explicit outbound profile links.
        for candidate in list(candidates.values())[:40]:
            await _fetch_candidate(client, candidate)
            possible_name = _candidate_name(candidate.title, candidate.handle)
            if possible_name:
                names.add(possible_name)

        # Profiles with the seed handle or strong name match become anchors before history analysis.
        for candidate in candidates.values():
            same_handle = _normalize_handle(candidate.handle) == _normalize_handle(seed_handle)
            possible_name = _candidate_name(candidate.title, candidate.handle)
            name_match = max((_name_similarity(possible_name, n) for n in names), default=0.0)
            if same_handle or name_match >= 0.92:
                known_profiles.add(candidate.url)

        # Git history is a high-value public source because removed social links remain attributable.
        github_candidates = [c for c in candidates.values() if c.platform == "github"]
        for github in github_candidates[:8]:
            historical, history_warnings = await _github_history_links(client, github.handle)
            warnings.extend(w for w in history_warnings if w not in warnings)
            for historical_url, sha in historical:
                platform = _platform_for_url(historical_url)
                if not platform:
                    continue
                handle = _profile_handle(historical_url, platform)
                historical_candidate = candidates.setdefault(
                    historical_url,
                    Candidate(
                        url=historical_url,
                        platform=platform,
                        handle=handle,
                        provenance="github_history",
                    ),
                )
                historical_candidate.provenance = "github_history"
                ev = Evidence(
                    id=new_id("ev"),
                    case_id=case_id,
                    source="GitHub public history",
                    collector="github-readme-history",
                    source_url=f"https://github.com/{github.handle}/{github.handle}/commit/{sha}",
                    excerpt=f"Historical public README explicitly linked {historical_url}",
                    metadata={
                        "github_handle": github.handle,
                        "commit": sha,
                        "discovered_profile": historical_url,
                    },
                    reliability=0.92,
                )
                store.add_evidence(ev)
                historical_candidate.evidence_ids.append(ev.id)
                evidence_added += 1
                known_profiles.add(historical_url)

        # Fetch metadata for any profiles discovered only through history.
        for candidate in candidates.values():
            if not candidate.title:
                await _fetch_candidate(client, candidate)

    confirmed = 0
    for canonical, candidate in candidates.items():
        score, reasons, strong = score_candidate(seed_handle, names, known_profiles, candidate)

        entity = Entity(
            id=new_id("ent"),
            case_id=case_id,
            kind="public_account",
            label=f"{candidate.platform} · @{candidate.handle}",
            canonical_key=f"public-account:{candidate.platform}:{_normalize_handle(candidate.handle)}",
            properties={
                "platform": candidate.platform,
                "handle": candidate.handle,
                "url": canonical,
                "display_name": _candidate_name(candidate.title, candidate.handle),
                "bio": candidate.description[:1000],
                "provenance": candidate.provenance,
            },
            confidence=max(0.35, score),
        )
        entity, was_created = store.upsert_entity(entity)
        created += int(was_created)

        if score >= 0.45 and strong and entity.id != root.id:
            store.add_edge(
                Edge(
                    id=new_id("edge"),
                    case_id=case_id,
                    source_id=root.id,
                    target_id=entity.id,
                    relation="possibly_same_public_identity",
                    confidence=score,
                    rationale=reasons,
                    evidence_ids=candidate.evidence_ids[:20],
                )
            )
            confirmed += 1

    if candidates:
        finding = Finding(
            id=new_id("finding"),
            case_id=case_id,
            category="public-identity-discovery",
            severity="info",
            title="Public identity candidates discovered",
            summary=(
                f"{len(candidates)} public profile candidate(s) were observed; "
                f"{confirmed} received a strong evidence-backed relation. "
                "Different usernames are resolved through public names, explicit backlinks and historical links; "
                "username similarity alone is never treated as identity proof."
            ),
            confidence=0.9 if confirmed else 0.62,
            evidence_ids=[
                evidence_id
                for candidate in candidates.values()
                for evidence_id in candidate.evidence_ids[:2]
            ][:30],
        )
        store.add_finding(finding)
        findings_added += 1

    if not names:
        warnings.append(
            "No stable public display-name anchor was recovered; different-handle discovery may be incomplete."
        )

    return created, evidence_added, findings_added, warnings
