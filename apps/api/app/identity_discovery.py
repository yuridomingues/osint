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
    publications: list[dict] = field(default_factory=list)


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
    anchor_texts: set[str] | None = None,
    known_external_hosts: set[str] | None = None,
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

    anchor_texts = anchor_texts or set()
    known_external_hosts = known_external_hosts or set()

    if candidate.description and anchor_texts:
        bio_match = max(
            (_name_similarity(candidate.description, text) for text in anchor_texts if len(text) >= 20),
            default=0.0,
        )
        if bio_match >= 0.62:
            score += 0.28
            reasons.append("public biography/content strongly overlaps an independently observed profile")
            if best_name >= 0.72:
                strong_signal = True
                reasons.append("name + biography provide two independent public identity signals")
        elif bio_match >= 0.48:
            score += 0.15
            reasons.append("public biography/content partially overlaps an independently observed profile")

    candidate_hosts = {
        (urlparse(url).hostname or "").casefold().removeprefix("www.")
        for url in candidate.outbound_links
        if _safe_outbound(url)
    }
    shared_external = {
        host for host in candidate_hosts & known_external_hosts
        if host and host not in {x.removeprefix("www.") for x in SAFE_PROFILE_HOSTS}
    }
    if shared_external:
        score += 0.36
        strong_signal = True
        reasons.append("candidate shares an external public domain with an observed profile")

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


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _public_links_from_mapping(data: dict) -> set[str]:
    links: set[str] = set()
    for key, value in data.items():
        key_l = str(key).casefold()
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            if any(token in key_l for token in ("url", "link", "website", "social", "linkedin", "twitter", "instagram")):
                safe = _safe_outbound(value)
                if safe:
                    links.add(safe)
        elif isinstance(value, (list, dict)) and any(
            token in key_l for token in ("social", "links", "identities")
        ):
            for nested in _walk_dicts(value):
                for nested_value in nested.values():
                    if isinstance(nested_value, str) and nested_value.startswith(("http://", "https://")):
                        safe = _safe_outbound(nested_value)
                        if safe:
                            links.add(safe)
    return links


def _substack_publication_url(item: dict) -> str:
    for key in ("custom_domain", "customDomain"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            host = value.strip().removeprefix("https://").removeprefix("http://").strip("/")
            if host:
                return f"https://{host}"

    for key in ("publication_url", "publicationUrl", "homepage_url", "homepageUrl", "url"):
        value = item.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            host = (urlparse(value).hostname or "").casefold()
            if host.endswith(".substack.com") or "substack.com" not in host:
                return value.split("#", 1)[0].rstrip("/")

    for key in ("subdomain", "publication_subdomain", "publicationSubdomain"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            subdomain = value.strip().casefold()
            if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", subdomain):
                return f"https://{subdomain}.substack.com"

    return ""


def _substack_publications_from_mapping(data: dict) -> list[dict]:
    publications: list[dict] = []
    seen: set[str] = set()

    for item in _walk_dicts(data):
        url = _substack_publication_url(item)
        name = _clean_text(str(item.get("name") or item.get("publication_name") or item.get("publicationName") or ""))
        publication_id = item.get("publication_id") or item.get("publicationId")

        # A publication must expose publication-specific addressing/ID information.
        if not url and not publication_id:
            continue
        if not name:
            continue

        key = url or f"id:{publication_id}"
        if key in seen:
            continue
        seen.add(key)

        description = _redact_contact(
            str(
                item.get("description")
                or item.get("hero_text")
                or item.get("heroText")
                or item.get("tagline")
                or ""
            )
        )
        publications.append(
            {
                "name": name,
                "url": url,
                "description": description,
                "publication_id": publication_id,
                "subdomain": item.get("subdomain"),
            }
        )

    return publications


async def _substack_public_profile(
    client: httpx.AsyncClient,
    handle: str,
) -> Candidate | None:
    handle = handle.lstrip("@").strip()
    if not handle:
        return None
    try:
        response = await client.get(
            f"https://substack.com/api/v1/user/{quote(handle)}/public_profile",
            headers={
                "Accept": "application/json",
                "Origin": "https://substack.com",
                "Referer": "https://substack.com/",
                "User-Agent": "Mozilla/5.0",
            },
        )
        if response.status_code != 200:
            return None
        data = response.json()
        if not isinstance(data, dict):
            return None
        actual_handle = str(data.get("handle") or handle).lstrip("@")
        name = _clean_text(str(data.get("name") or ""))
        bio = _redact_contact(str(data.get("bio") or data.get("profile_set_up_at") or ""))
        candidate = Candidate(
            url=f"https://substack.com/@{actual_handle}",
            platform="substack",
            handle=actual_handle,
            title=f"{name} | Substack" if name else f"@{actual_handle} | Substack",
            description=bio,
            outbound_links=_public_links_from_mapping(data),
            provenance="substack_public_profile",
            publications=_substack_publications_from_mapping(data),
        )
        return candidate
    except Exception:
        return None


async def _substack_people_search(
    client: httpx.AsyncClient,
    query: str,
) -> tuple[list[Candidate], str | None]:
    try:
        response = await client.get(
            "https://substack.com/api/v1/search/explore/web",
            params={"query": query},
            headers={
                "Accept": "application/json",
                "Origin": "https://substack.com",
                "Referer": "https://substack.com/search",
                "User-Agent": "Mozilla/5.0",
            },
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return [], f"Substack public search unavailable: {type(exc).__name__}"

    handles: list[str] = []
    seen: set[str] = set()
    for item in _walk_dicts(data):
        raw_handle = item.get("handle")
        if not isinstance(raw_handle, str):
            continue
        handle = raw_handle.lstrip("@").strip()
        if not handle or handle in seen:
            continue
        # User/profile objects normally expose a person-like handle/name/photo/bio.
        # Publication objects generally use a subdomain instead of a user handle.
        personish = any(key in item for key in ("name", "photo_url", "bio", "profile_url"))
        if personish:
            seen.add(handle)
            handles.append(handle)
        if len(handles) >= 20:
            break

    candidates: list[Candidate] = []
    for handle in handles:
        candidate = await _substack_public_profile(client, handle)
        if candidate:
            candidate.provenance = "substack_search"
            candidates.append(candidate)
    return candidates, None


async def _fetch_candidate(client: httpx.AsyncClient, candidate: Candidate) -> Candidate:
    if candidate.platform == "substack":
        public_profile = await _substack_public_profile(client, candidate.handle)
        if public_profile:
            candidate.title = public_profile.title or candidate.title
            candidate.description = public_profile.description or candidate.description
            candidate.outbound_links.update(public_profile.outbound_links)
            if public_profile.publications:
                candidate.publications = public_profile.publications

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
        canonical_key=(
            f"public-account:{seed_platform}:{_normalize_handle(seed_handle)}"
            if seed_platform
            else f"public-account:seed:{_normalize_handle(seed_handle)}"
        ),
        properties={"handle": seed_handle, "platform": seed_platform or "unknown", "url": seed_url},
        confidence=0.98,
    )
    root, was_created = store.upsert_entity(root)
    created += int(was_created)

    known_profiles: set[str] = set()
    if seed_url:
        known_profiles.add(seed_url)

    names: set[str] = set()
    anchor_texts: set[str] = set()
    known_external_hosts: set[str] = set()
    candidates: dict[str, Candidate] = {}
    if seed_url and seed_platform:
        candidates[seed_url] = Candidate(
            url=seed_url,
            platform=seed_platform,
            handle=seed_handle,
            provenance="seed",
        )

    async with httpx.AsyncClient(
        timeout=SEARCH_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8"},
        follow_redirects=True,
    ) as client:
        # Direct public Substack handle resolution is cheap and useful even when
        # the seed came from another platform.
        substack_seed = await _substack_public_profile(client, seed_handle)
        if substack_seed:
            candidates.setdefault(substack_seed.url, substack_seed)

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
                is_seed_profile = bool(seed_url and canonical == seed_url)
                is_seed_platform_match = bool(
                    seed_platform
                    and platform == seed_platform
                    and _normalize_handle(handle) == _normalize_handle(seed_handle)
                )
                if possible_name and (is_seed_profile or is_seed_platform_match or not seed_url):
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

        # Resolve the supplied seed before cross-handle pivots. If the platform exposes
        # a public title/bio, this gives us a stable name or text anchor without guessing.
        for candidate in list(candidates.values()):
            is_seed_profile = bool(seed_url and candidate.url == seed_url)
            is_seed_platform_match = bool(
                seed_platform
                and candidate.platform == seed_platform
                and _normalize_handle(candidate.handle) == _normalize_handle(seed_handle)
            )
            if not (is_seed_profile or is_seed_platform_match):
                continue
            await _fetch_candidate(client, candidate)
            possible_name = _candidate_name(candidate.title, candidate.handle)
            if possible_name:
                names.add(possible_name)

        # A different handle can still be discoverable through stable public identity anchors.
        # Use names observed from the supplied seed, not names manufactured from a username.
        for name in sorted(names)[:3]:
            substack_candidates, substack_warning = await _substack_people_search(client, name)
            if substack_warning and substack_warning not in warnings:
                warnings.append(substack_warning)
            for candidate in substack_candidates:
                existing = candidates.setdefault(candidate.url, candidate)
                if not existing.title:
                    existing.title = candidate.title
                if not existing.description:
                    existing.description = candidate.description
                existing.outbound_links.update(candidate.outbound_links)
                ev = Evidence(
                    id=new_id("ev"),
                    case_id=case_id,
                    source="Substack public profile search",
                    collector="substack-public-search",
                    source_url=candidate.url,
                    excerpt=_redact_contact(candidate.title),
                    metadata={
                        "query": name,
                        "platform": "substack",
                        "handle": candidate.handle,
                    },
                    reliability=0.72,
                )
                store.add_evidence(ev)
                existing.evidence_ids.append(ev.id)
                evidence_added += 1

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
            is_seed_profile = bool(seed_url and candidate.url == seed_url)
            is_seed_platform_match = bool(
                seed_platform
                and candidate.platform == seed_platform
                and _normalize_handle(candidate.handle) == _normalize_handle(seed_handle)
            )
            if possible_name and (is_seed_profile or is_seed_platform_match or not seed_url):
                names.add(possible_name)

        # Only the supplied seed profile is a trusted initial anchor. Reusing a username
        # on another platform remains a weak lead until another public signal connects it.
        for candidate in candidates.values():
            is_seed_profile = bool(seed_url and candidate.url == seed_url)
            is_seed_platform_match = bool(
                seed_platform
                and candidate.platform == seed_platform
                and _normalize_handle(candidate.handle) == _normalize_handle(seed_handle)
            )
            if is_seed_profile or is_seed_platform_match:
                known_profiles.add(candidate.url)
                if len(candidate.description) >= 20:
                    anchor_texts.add(candidate.description)
                for outbound in candidate.outbound_links:
                    host = (urlparse(outbound).hostname or "").casefold().removeprefix("www.")
                    if host and host not in {x.removeprefix("www.") for x in SAFE_PROFILE_HOSTS}:
                        known_external_hosts.add(host)

        # Git history is a high-value public source because removed social links remain attributable.
        github_candidates = [c for c in candidates.values() if c.platform == "github"]
        for github in github_candidates[:8]:
            historical, history_warnings = await _github_history_links(client, github.handle)
            warnings.extend(w for w in history_warnings if w not in warnings)

            # Git history becomes attribution evidence only when it points back to an
            # already trusted profile from this case. This blocks same-name GitHub false positives.
            anchored_links = {
                historical_url for historical_url, _ in historical if historical_url in known_profiles
            }
            history_is_anchored = bool(anchored_links)
            if history_is_anchored:
                github.provenance = "github_history"
                known_profiles.add(github.url)

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
                        provenance=(
                            "github_history" if history_is_anchored else "github_history_unanchored"
                        ),
                    ),
                )
                if history_is_anchored:
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
                        "history_anchored_to_seed": history_is_anchored,
                    },
                    reliability=0.92 if history_is_anchored else 0.68,
                )
                store.add_evidence(ev)
                historical_candidate.evidence_ids.append(ev.id)
                if historical_url in anchored_links:
                    github.evidence_ids.append(ev.id)
                evidence_added += 1
                if history_is_anchored:
                    known_profiles.add(historical_url)

        # Fetch metadata for any profiles discovered only through history.
        for candidate in candidates.values():
            if not candidate.title:
                await _fetch_candidate(client, candidate)

    confirmed = 0
    accepted_substack: list[tuple[Entity, Candidate, float, list[str]]] = []
    for canonical, candidate in candidates.items():
        score, reasons, strong = score_candidate(
            seed_handle,
            names,
            known_profiles,
            candidate,
            anchor_texts=anchor_texts,
            known_external_hosts=known_external_hosts,
        )

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

        if entity.id != root.id and reasons:
            if score >= 0.45 and strong:
                relation = "possibly_same_public_identity"
                confirmed += 1
            elif score >= 0.25:
                relation = "identity_candidate"
            else:
                relation = ""

            if relation:
                store.add_edge(
                    Edge(
                        id=new_id("edge"),
                        case_id=case_id,
                        source_id=root.id,
                        target_id=entity.id,
                        relation=relation,
                        confidence=score,
                        rationale=reasons,
                        evidence_ids=candidate.evidence_ids[:20],
                    )
                )

        is_seed_profile = bool(seed_url and canonical == seed_url)
        is_confirmed_identity = score >= 0.45 and strong
        if candidate.platform == "substack" and candidate.publications and (
            is_seed_profile or is_confirmed_identity
        ):
            accepted_substack.append((entity, candidate, score, reasons))

    # Model author/profile and publication as separate entities. A newsletter title can
    # be completely unrelated to the author's username (e.g. @author -> "Escassez").
    for profile_entity, candidate, identity_score, identity_reasons in accepted_substack:
        for publication in candidate.publications[:20]:
            pub_url = publication.get("url") or ""
            pub_name = publication.get("name") or pub_url or "Substack publication"
            pub_key = (
                f"publication:substack:{pub_url.casefold()}"
                if pub_url
                else f"publication:substack:id:{publication.get('publication_id')}"
            )
            pub_entity = Entity(
                id=new_id("ent"),
                case_id=case_id,
                kind="publication",
                label=pub_name,
                canonical_key=pub_key,
                properties={
                    "platform": "substack",
                    "url": pub_url,
                    "description": publication.get("description") or "",
                    "publication_id": publication.get("publication_id"),
                    "owner_handle": candidate.handle,
                },
                confidence=0.95,
            )
            pub_entity, was_created = store.upsert_entity(pub_entity)
            created += int(was_created)

            ev = Evidence(
                id=new_id("ev"),
                case_id=case_id,
                source="Substack public profile",
                collector="substack-public-profile",
                source_url=candidate.url,
                excerpt=f"Public Substack profile lists publication: {pub_name}",
                metadata={
                    "author_handle": candidate.handle,
                    "publication_name": pub_name,
                    "publication_url": pub_url,
                    "publication_id": publication.get("publication_id"),
                },
                reliability=0.88,
            )
            store.add_evidence(ev)
            evidence_added += 1

            store.add_edge(
                Edge(
                    id=new_id("edge"),
                    case_id=case_id,
                    source_id=profile_entity.id,
                    target_id=pub_entity.id,
                    relation="publishes",
                    confidence=0.96,
                    rationale=["publication is listed on the public Substack author profile"],
                    evidence_ids=[ev.id],
                )
            )

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
