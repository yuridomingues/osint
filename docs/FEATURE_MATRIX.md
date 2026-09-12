# VIGIL feature matrix

This document separates product capability from data-provider coverage.

## Implemented

| Capability | Status | Notes |
|---|---|---|
| Investigation cases | Ready | target, objective, scope acknowledgement, status |
| Entity-link graph | Ready | Cytoscape, filters, layouts, relation confidence |
| Multi-select & analyst clusters | Ready | non-destructive grouping and detach |
| Relation review | Ready | confirmed, rejected, needs-review |
| Saved graph views | Ready | persisted filters/layout |
| Evidence ledger | Ready | source, collector, time, reliability, SHA-256 |
| Evidence snapshots | Ready | immutable serialized evidence snapshot + hash |
| Pins / curation | Ready | entities, edges, evidence, findings, notes, hypotheses |
| Full & curated reports | Ready | print-ready HTML/PDF workflow, Markdown, CSV |
| JSON / GraphML export | Ready | raw graph portability |
| Timeline | Ready | automatic evidence chronology + manual events |
| Map | Ready | city-level/coarse public context only |
| Notes | Ready | tags and audit logging |
| Hypotheses | Ready | status, confidence, counterpoints |
| Findings | Ready | separate observation from assessment |
| Audit trail | Ready | analyst mutations and collection/import actions |
| Domain passive OSINT | Ready | Certificate Transparency, RDAP, Wayback |
| URL passive OSINT | Ready | normalization + Wayback |
| IP passive context | Ready | public allocation/RDAP; no precise-person geolocation |
| Public identity discovery | Ready | cross-handle candidates from public web search, metadata, backlinks, external domains and GitHub history |
| Image evidence | Ready | local SHA-256, aHash/dHash, safe EXIF, optional C2PA parsing, local media correlation |
| Reverse image search | Optional | TinEye API adapter for exact/modified copies; no facial recognition |
| Sherlock import | Ready | public account CSV |
| Maigret import | Ready | public account JSON/NDJSON |
| Subfinder import | Ready | organizational/domain JSONL |
| OWASP Amass import | Ready | host/IP passive asset graph |
| SpiderFoot import | Ready | infrastructure event types only |
| Public post coordination | Ready | exact normalized-content clusters + temporal window |
| Impersonation assessment | Ready | explainable multi-signal scoring |
| Docker | Ready | web + API + persistent SQLite |
| CI | Ready | API pytest + frontend production build |

## Adapter roadmap

These are integration points rather than reasons to fork upstream projects.

| Capability | Preferred implementation |
|---|---|
| OpenCTI | STIX 2.1 import/export |
| MISP | MISP JSON event import/export |
| urlscan.io | API enrichment for URLs/domains |
| VirusTotal | optional domain/URL enrichment |
| Censys/Shodan | optional organization/infrastructure enrichment |
| ExifTool | deeper metadata coverage beyond Pillow-safe EXIF |
| C2PA validation worker | c2patool-backed full validation and trust-chain reporting |
| Visual OCR | text extraction from supplied evidence, with language packs and provenance |
| Video evidence | frame extraction, keyframe hashing and reverse-image pivots |
| Media corpus index | local perceptual-hash index across collected public evidence |
| Object storage | raw source bundle storage for larger teams |
| Multi-user | PostgreSQL + authentication/RBAC |
| Queue/workers | isolated collectors via job queue |

## Deliberate boundaries

VIGIL is not designed to:

- create automated dossiers on private people;
- use private contact details as automatic identity pivots;
- perform mass email/phone/name lookup;
- use leaked credential databases;
- identify private people using face recognition;
- surface precise residential locations;
- perform offensive social engineering;
- automate influence operations;
- bypass authentication or access controls.

The analyst-workbench features remain useful for brand protection, public-account verification, CTI, misinformation analysis, fraud/impersonation triage and authorized organizational research.

## Product parity vs provider parity

A local/open workbench can reproduce the **workflow layer** of commercial OSINT products: one selector/case, entity graph, timeline, geospatial context, evidence provenance, correlation, curation and reporting.

It cannot honestly claim the same **provider coverage** as a commercial platform that pays for proprietary APIs and maintains private integrations. VIGIL therefore treats provider modules as replaceable adapters and exposes their provenance instead of hiding the source behind a single opaque result.
