# VIGIL OSINT gaps — September 2026

This document records gaps found by comparing VIGIL with current public-source investigation workflows and contemporary OSINT platforms.

## Implemented in v0.4

### Image evidence
- local SHA-256
- 64-bit average hash (aHash)
- 64-bit difference hash (dHash)
- dimensions / format / byte size
- safe EXIF extraction
- precise GPS redaction for person/account investigations
- C2PA marker detection and optional c2patool parsing
- media-hash correlation against entities already present in a case
- optional TinEye reverse-image adapter for exact/modified copies
- graph pivots from image -> public URL -> public account when the matched page is a public profile URL

This feature intentionally does **not** identify people from facial features.

## High-priority gaps

### 1. Multi-provider reverse-image orchestration
A single reverse-image index is incomplete. Professional visual verification benefits from multiple independent engines and source families.

VIGIL currently has:
- TinEye API adapter

Still needed:
- provider abstraction with normalized result schema
- per-provider confidence/provenance
- de-duplication of backlinks
- earliest-seen / largest-image sorting
- result screenshots / archival snapshots

### 2. Full C2PA / Content Credentials validation
C2PA 2.4 is now a first-class provenance standard. VIGIL currently detects markers and can use c2patool if installed.

Still needed:
- ship c2patool in a dedicated worker/container
- validate manifests against trust lists
- persist validation statuses and signer information
- represent ingredients / edit lineage in the graph
- distinguish missing credentials from invalid credentials

### 3. Deeper metadata extraction
Pillow covers common EXIF but not the full breadth of EXIF/IPTC/XMP/JUMBF/QuickTime metadata.

Still needed:
- ExifTool worker
- normalized metadata schema
- provenance-safe redaction policy
- file-type-specific metadata panels

### 4. Visual text / OCR
Text in screenshots, signs, documents and UI captures is often the best pivot.

Still needed:
- OCR for supplied evidence
- language detection / selectable language packs
- bounding boxes and confidence
- extracted URL/domain/username pivots
- preserve original image region for every extracted string

### 5. Video evidence
Modern investigations routinely reduce video to searchable frames.

Still needed:
- FFmpeg keyframe extraction
- scene-change detection
- frame SHA-256 / perceptual hashes
- reverse-image search on selected frames
- metadata and C2PA for video containers
- timeline mapping from frame timestamps

### 6. Local media corpus
VIGIL can compare an uploaded image with media hashes already imported into entities, but it does not yet maintain a dedicated visual index.

Still needed:
- content-addressed object store
- perceptual-hash index
- crop/resize robust matching
- source URL + capture timestamp per media object
- automatic duplicate/derivative clusters

### 7. Evidence preservation
URLs can disappear after an investigation begins.

Still needed:
- WARC capture or equivalent immutable page bundle
- HTML + screenshot + headers
- SHA-256 manifest of captured artifacts
- capture timestamp and redirect chain
- reproducible collector version metadata

### 8. Public-source query planner
VIGIL has collectors, but the analyst still manually chooses many pivots.

Still needed:
- graph-driven next-pivot suggestions
- budgets/rate limits per provider
- stop conditions
- source diversity requirement before raising confidence
- explainable reason for every automatic pivot

### 9. Temporal entity resolution
Identity and infrastructure attributes change.

Still needed:
- valid-from / valid-to on observations
- freshness weighting
- historical aliases as first-class entities
- contradiction handling instead of overwriting values

### 10. Infrastructure enrichment
Current built-ins cover CT/RDAP/Wayback plus structured imports, but commercial CTI workflows usually add:
- passive DNS
- reputation / malware verdicts
- observed URLs
- ASN / service exposure
- CVE context

These should remain optional adapters with provider provenance.

## Methodology principles

1. Observation is not attribution.
2. A search result is a lead, not an identity verdict.
3. Reverse-image matching is about the visual asset; it is not facial identification.
4. Every derived relation must retain its source evidence.
5. Missing metadata is not evidence that metadata never existed.
6. Provider disagreement should remain visible.
7. Preserve the original artifact hash before transformations.
8. Prefer independent corroboration over a larger number of duplicated providers.

## Current references

- OSINT Industries, Mid Summer Update (August 2026): image search workflow combining reverse image, EXIF, C2PA, image analysis, pivots and curated reports.
- C2PA Technical Specification 2.4 (April 2026): current Content Credentials provenance model.
- Content Authenticity Initiative c2pa-rs / c2patool: current open-source C2PA parsing/validation implementation.
- ExifTool: broad EXIF/IPTC/XMP/ICC/C2PA metadata coverage.
- TinEye API: programmatic reverse-image search across its web image index.
- Bellingcat visual-investigation methodology: reverse image search, visual analysis, source preservation and corroboration remain core verification techniques.
