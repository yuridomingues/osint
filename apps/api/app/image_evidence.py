from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError

from .models import Edge, Entity, Evidence, Finding, ImageEvidenceImport, new_id
from .store import Store


MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

SOCIAL_HOSTS = {
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    "x.com": "x",
    "www.x.com": "x",
    "twitter.com": "x",
    "www.twitter.com": "x",
    "github.com": "github",
    "www.github.com": "github",
    "linkedin.com": "linkedin",
    "www.linkedin.com": "linkedin",
    "substack.com": "substack",
    "www.substack.com": "substack",
    "medium.com": "medium",
    "www.medium.com": "medium",
    "tiktok.com": "tiktok",
    "www.tiktok.com": "tiktok",
    "youtube.com": "youtube",
    "www.youtube.com": "youtube",
}

SAFE_EXIF_KEYS = {
    "Make",
    "Model",
    "Software",
    "DateTime",
    "DateTimeOriginal",
    "DateTimeDigitized",
    "Orientation",
    "LensModel",
    "Artist",
    "Copyright",
    "ImageDescription",
}


def _decode_image(payload: ImageEvidenceImport) -> bytes:
    raw = payload.data_base64.strip()
    if raw.startswith("data:"):
        try:
            raw = raw.split(",", 1)[1]
        except IndexError as exc:
            raise ValueError("Invalid image data URI") from exc
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("Invalid base64 image payload") from exc
    if not data:
        raise ValueError("Image payload is empty")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds the 12 MB case-evidence limit")
    return data


def _hex_bits(bits: list[bool]) -> str:
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    width = max(1, (len(bits) + 3) // 4)
    return f"{value:0{width}x}"


def average_hash(image: Image.Image, size: int = 8) -> str:
    gray = ImageOps.grayscale(image).resize((size, size), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    mean = sum(pixels) / len(pixels)
    return _hex_bits([value >= mean for value in pixels])


def difference_hash(image: Image.Image, size: int = 8) -> str:
    gray = ImageOps.grayscale(image).resize((size + 1, size), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    bits: list[bool] = []
    for row in range(size):
        offset = row * (size + 1)
        for col in range(size):
            bits.append(pixels[offset + col] > pixels[offset + col + 1])
    return _hex_bits(bits)


def hamming_hex(left: str, right: str) -> int | None:
    try:
        a = int(left, 16)
        b = int(right, 16)
    except (TypeError, ValueError):
        return None
    return (a ^ b).bit_count()


def _safe_exif(image: Image.Image) -> dict:
    result: dict[str, object] = {}
    try:
        exif = image.getexif()
    except Exception:
        return result

    if not exif:
        return result

    gps_present = False
    for key, value in exif.items():
        name = ExifTags.TAGS.get(key, str(key))
        if name == "GPSInfo":
            gps_present = True
            continue
        if name not in SAFE_EXIF_KEYS:
            continue
        if isinstance(value, bytes):
            value = value[:128].hex()
        elif not isinstance(value, (str, int, float, bool, type(None))):
            value = str(value)
        result[name] = value

    if gps_present:
        # Deliberately do not persist precise coordinates in person/account workflows.
        result["GPSInfo"] = "present_redacted"

    return result


def _c2pa_summary(data: bytes, suffix: str) -> dict:
    marker_present = b"c2pa" in data.lower() or b"jumb" in data.lower()
    enabled = os.getenv("VIGIL_ENABLE_C2PA_TOOL", "1").strip().casefold() not in {"0", "false", "no"}
    tool = shutil.which("c2patool") if enabled else None
    summary: dict[str, object] = {
        "marker_present": marker_present,
        "tool_available": bool(tool),
        "manifest_present": False,
        "validation": "not_checked",
    }
    if not tool:
        return summary

    path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix or ".img", delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        proc = subprocess.run(
            [tool, path],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        output = proc.stdout.strip()
        if proc.returncode == 0 and output:
            parsed = json.loads(output)
            summary["manifest_present"] = bool(parsed)
            summary["validation"] = "parsed"
            if isinstance(parsed, dict):
                active = parsed.get("active_manifest") or parsed.get("activeManifest")
                if active:
                    summary["active_manifest"] = str(active)
                validation = parsed.get("validation_status") or parsed.get("validationStatus")
                if validation is not None:
                    summary["validation_status"] = validation
        elif marker_present:
            summary["validation"] = "marker_only"
        else:
            summary["validation"] = "none"
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        summary["validation"] = "tool_error" if marker_present else "none"
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass
    return summary


def analyze_image_bytes(data: bytes, filename: str = "image") -> dict:
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds the 12 MB case-evidence limit")
    try:
        with Image.open(io.BytesIO(data)) as opened:
            opened.load()
            image = ImageOps.exif_transpose(opened).convert("RGB")
            fmt = opened.format or "unknown"
            width, height = image.size
            exif = _safe_exif(opened)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Unsupported or unsafe image file") from exc

    if width * height > MAX_PIXELS:
        raise ValueError("Image exceeds the 40 megapixel safety limit")

    sha256 = hashlib.sha256(data).hexdigest()
    return {
        "filename": filename,
        "sha256": sha256,
        "byte_size": len(data),
        "format": fmt,
        "width": width,
        "height": height,
        "aspect_ratio": round(width / height, 5) if height else None,
        "ahash": average_hash(image),
        "dhash": difference_hash(image),
        "exif": exif,
        "c2pa": _c2pa_summary(data, Path(filename).suffix),
    }


def _normalize_media_hash(value: str) -> tuple[str, str] | None:
    text = (value or "").strip().casefold()
    if not text:
        return None
    if ":" in text:
        kind, digest = text.split(":", 1)
        if kind in {"sha256", "ahash", "dhash"} and re.fullmatch(r"[0-9a-f]+", digest):
            return kind, digest
    if re.fullmatch(r"[0-9a-f]{64}", text):
        return "sha256", text
    if re.fullmatch(r"[0-9a-f]{16}", text):
        return "dhash", text
    return None


def _entity_media_matches(entity: Entity, analysis: dict) -> tuple[float, list[str]]:
    raw = entity.properties.get("media_hashes")
    if not isinstance(raw, list):
        return 0.0, []

    best = 0.0
    reasons: list[str] = []
    for value in raw:
        if not isinstance(value, str):
            continue
        parsed = _normalize_media_hash(value)
        if not parsed:
            continue
        kind, digest = parsed
        if kind == "sha256" and digest == analysis["sha256"]:
            best = max(best, 1.0)
            reasons.append("exact SHA-256 media match")
        elif kind in {"dhash", "ahash"}:
            distance = hamming_hex(digest, str(analysis[kind]))
            if distance is None:
                continue
            if distance <= 4:
                best = max(best, 0.94)
                reasons.append(f"{kind} perceptual distance {distance}/64")
            elif distance <= 8:
                best = max(best, 0.82)
                reasons.append(f"{kind} perceptual distance {distance}/64")
    return best, list(dict.fromkeys(reasons))


def _prepare_tineye_image(data: bytes) -> bytes:
    # TinEye currently accepts max 1 MB query images. Re-encode while preserving enough
    # detail for duplicate/derivative matching.
    if len(data) <= 950_000:
        return data
    with Image.open(io.BytesIO(data)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        image.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
        quality = 88
        while quality >= 55:
            out = io.BytesIO()
            image.save(out, format="JPEG", quality=quality, optimize=True)
            blob = out.getvalue()
            if len(blob) <= 950_000:
                return blob
            quality -= 7
    raise ValueError("Could not prepare image for reverse-image provider")


def _extract_backlink_url(backlink: object) -> str:
    if isinstance(backlink, str) and backlink.startswith(("http://", "https://")):
        return backlink
    if isinstance(backlink, dict):
        for key in ("backlink", "url", "page_url", "pageUrl"):
            value = backlink.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
    return ""


async def tineye_reverse_search(data: bytes, filename: str) -> tuple[list[dict], str | None]:
    api_key = os.getenv("TINEYE_API_KEY", "").strip()
    if not api_key:
        return [], "TinEye reverse-image provider is not configured (TINEYE_API_KEY)."

    try:
        query = _prepare_tineye_image(data)
    except ValueError as exc:
        return [], str(exc)

    endpoint = os.getenv("TINEYE_API_URL", "https://api.tineye.com/rest/").rstrip("/") + "/search/"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), follow_redirects=True) as client:
            response = await client.post(
                endpoint,
                headers={"x-api-key": api_key, "User-Agent": "VIGIL-OSINT/0.4"},
                data={
                    "offset": "0",
                    "limit": "30",
                    "backlink_limit": "30",
                    "sort": "score",
                    "order": "desc",
                },
                files={"image": (filename or "query.jpg", query, "image/jpeg")},
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        return [], f"TinEye reverse-image search unavailable: {type(exc).__name__}"

    matches: list[dict] = []
    raw_matches = payload.get("results", {}).get("matches", []) if isinstance(payload, dict) else []
    for item in raw_matches:
        if not isinstance(item, dict):
            continue
        backlinks = []
        for backlink in item.get("backlinks") or []:
            url = _extract_backlink_url(backlink)
            if url:
                backlinks.append(url)
        matches.append(
            {
                "score": item.get("score"),
                "domain": item.get("domain"),
                "image_url": item.get("image_url"),
                "backlinks": list(dict.fromkeys(backlinks))[:30],
                "width": item.get("width"),
                "height": item.get("height"),
                "tags": item.get("tags") or [],
            }
        )
    return matches, None


def _profile_from_url(url: str) -> tuple[str, str] | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    platform = SOCIAL_HOSTS.get(host)
    if not platform:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return None
    if platform == "linkedin":
        if len(parts) < 2 or parts[0] != "in":
            return None
        return platform, parts[1]
    handle = parts[0].lstrip("@")
    if not handle or handle in {"explore", "search", "home", "share", "status"}:
        return None
    return platform, handle


async def attach_image_evidence(
    store: Store,
    case_id: str,
    payload: ImageEvidenceImport,
) -> dict:
    data = _decode_image(payload)
    analysis = analyze_image_bytes(data, payload.filename)

    image_entity = Entity(
        id=new_id("ent"),
        case_id=case_id,
        kind="image",
        label=payload.filename or "image evidence",
        canonical_key=f"image:sha256:{analysis['sha256']}",
        properties={
            "sha256": analysis["sha256"],
            "ahash": analysis["ahash"],
            "dhash": analysis["dhash"],
            "format": analysis["format"],
            "width": analysis["width"],
            "height": analysis["height"],
            "byte_size": analysis["byte_size"],
            "exif": analysis["exif"],
            "c2pa": analysis["c2pa"],
        },
        confidence=1.0,
    )
    image_entity, image_created = store.upsert_entity(image_entity)

    ev = Evidence(
        id=new_id("ev"),
        case_id=case_id,
        source="Uploaded image evidence",
        collector="image-evidence",
        excerpt=(
            f"{analysis['format']} {analysis['width']}x{analysis['height']} · "
            f"SHA-256 {analysis['sha256'][:16]}…"
        ),
        metadata={
            "filename": payload.filename,
            "content_type": payload.content_type,
            "analysis": analysis,
        },
        reliability=1.0,
        content_hash=analysis["sha256"],
    )
    store.add_evidence(ev)

    local_matches: list[dict] = []
    graph = store.graph(case_id)
    if graph:
        for entity in graph.entities:
            if entity.id == image_entity.id:
                continue
            confidence, reasons = _entity_media_matches(entity, analysis)
            if confidence <= 0:
                continue
            store.add_edge(
                Edge(
                    id=new_id("edge"),
                    case_id=case_id,
                    source_id=entity.id,
                    target_id=image_entity.id,
                    relation="reuses_image",
                    confidence=confidence,
                    rationale=reasons,
                    evidence_ids=[ev.id],
                )
            )
            local_matches.append(
                {
                    "entity_id": entity.id,
                    "label": entity.label,
                    "confidence": confidence,
                    "reasons": reasons,
                }
            )

    provider_matches: list[dict] = []
    warning: str | None = None
    if payload.search_web:
        provider_matches, warning = await tineye_reverse_search(data, payload.filename)

        for match in provider_matches[:30]:
            for backlink in match.get("backlinks", [])[:20]:
                parsed = urlparse(backlink)
                host = (parsed.hostname or "").casefold().removeprefix("www.")
                if not host:
                    continue
                url_entity = Entity(
                    id=new_id("ent"),
                    case_id=case_id,
                    kind="url",
                    label=backlink,
                    canonical_key=f"url:{backlink}",
                    properties={
                        "host": host,
                        "reverse_image_provider": "tineye",
                        "provider_score": match.get("score"),
                        "matched_image_url": match.get("image_url"),
                    },
                    confidence=0.82,
                )
                url_entity, _ = store.upsert_entity(url_entity)
                match_ev = Evidence(
                    id=new_id("ev"),
                    case_id=case_id,
                    source="TinEye API",
                    collector="reverse-image-tineye",
                    source_url=backlink,
                    excerpt=f"Reverse-image match observed on {host}",
                    metadata={
                        "score": match.get("score"),
                        "domain": match.get("domain"),
                        "image_url": match.get("image_url"),
                        "tags": match.get("tags"),
                    },
                    reliability=0.78,
                    content_hash=analysis["sha256"],
                )
                store.add_evidence(match_ev)
                store.add_edge(
                    Edge(
                        id=new_id("edge"),
                        case_id=case_id,
                        source_id=image_entity.id,
                        target_id=url_entity.id,
                        relation="reverse_image_match",
                        confidence=0.82,
                        rationale=[
                            "same/modified image returned by reverse-image provider",
                            "this is media matching, not facial identification",
                        ],
                        evidence_ids=[ev.id, match_ev.id],
                    )
                )

                profile = _profile_from_url(backlink)
                if profile:
                    platform, handle = profile
                    account = Entity(
                        id=new_id("ent"),
                        case_id=case_id,
                        kind="public_account",
                        label=f"{platform} · @{handle}",
                        canonical_key=f"public-account:{platform}:{handle.casefold()}",
                        properties={
                            "platform": platform,
                            "handle": handle,
                            "profile_url": backlink,
                            "discovery": "reverse-image copy match",
                        },
                        confidence=0.78,
                    )
                    account, _ = store.upsert_entity(account)
                    store.add_edge(
                        Edge(
                            id=new_id("edge"),
                            case_id=case_id,
                            source_id=account.id,
                            target_id=image_entity.id,
                            relation="published_image",
                            confidence=0.78,
                            rationale=[
                                "reverse-image result URL maps to a public profile path",
                                "relation concerns image publication, not identity from facial features",
                            ],
                            evidence_ids=[match_ev.id],
                        )
                    )

    finding = Finding(
        id=new_id("finding"),
        case_id=case_id,
        category="image-evidence",
        severity="info",
        title="Image evidence analyzed",
        summary=(
            f"Computed SHA-256, aHash and dHash for {payload.filename or 'image'}; "
            f"EXIF fields: {len(analysis['exif'])}; "
            f"local media matches: {len(local_matches)}; "
            f"reverse-image matches: {len(provider_matches)}. "
            "No facial recognition or biometric identity inference was performed."
        ),
        confidence=1.0,
        evidence_ids=[ev.id],
    )
    store.add_finding(finding)

    store.audit(
        case_id,
        "image.analyzed",
        "entity",
        image_entity.id,
        {
            "sha256": analysis["sha256"],
            "search_web": payload.search_web,
            "provider": "tineye" if payload.search_web else None,
            "local_matches": len(local_matches),
            "provider_matches": len(provider_matches),
        },
    )

    return {
        "entity_id": image_entity.id,
        "entity_created": image_created,
        "evidence_id": ev.id,
        "analysis": analysis,
        "local_matches": local_matches,
        "reverse_image_matches": provider_matches,
        "warning": warning,
    }
