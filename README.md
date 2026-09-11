# VIGIL OSINT Workbench

VIGIL is a local-first, provenance-first OSINT investigation workbench.

It centralizes public-source collection, tool imports, entity correlation, analyst reasoning and reporting into a single case. The architecture is intentionally closer to a professional investigation platform than to a folder of unrelated OSINT scripts.

> VIGIL is designed for legitimate public-source research, brand protection, CTI, verification, misinformation analysis and authorized organizational investigations. It does not automate dossiers on private people, doxxing, credential collection, offensive social engineering or influence operations.

## Current product

### Investigation workspace

Each case includes:

- **Graph** — entity-link analysis with confidence and rationale.
- **Evidence** — provenance ledger with source, collector, timestamp, reliability and hash.
- **Findings** — assessments kept separate from raw observations.
- **Timeline** — automatically generated evidence chronology plus analyst events.
- **Map** — coarse/city-level public geospatial context.
- **Analysis** — notes, hypotheses, confidence, status and counterpoints.
- **Report builder** — pin exactly what belongs in the final report.
- **Modules** — built-in collectors and normalized adapters.
- **Audit** — investigation mutation trail.

### Graph features

- search;
- entity-type filters;
- confidence threshold;
- force/circle/grid/concentric layouts;
- hide rejected relationships;
- relation review: confirmed / rejected / needs review;
- multi-select;
- non-destructive analyst clusters;
- split/detach cluster members;
- persistent saved views;
- entity/edge pinning.

### Public-source collection

Built in:

- Certificate Transparency;
- RDAP domain registration context;
- Internet Archive / Wayback;
- public IP allocation RDAP;
- URL archive history.

Imports/adapters:

- Sherlock CSV;
- Maigret JSON / NDJSON;
- ProjectDiscovery Subfinder JSONL;
- OWASP Amass JSON;
- SpiderFoot infrastructure CSV;
- generic VIGIL public-account observations;
- public-post datasets for coordinated-behavior analysis.

Subfinder/Amass/SpiderFoot adapters are limited to domain/organization cases. SpiderFoot imports deliberately skip person/contact event types.

### Analysis

- conservative account correlation;
- shared-domain/media multi-signal edges;
- explainable fake/impersonation scoring;
- synchronized identical-content detection;
- explicit distinction between indicator and attribution;
- relation review state;
- hypotheses and counter-hypotheses;
- notes/tags;
- snapshots;
- evidence and mutation audit.

### Reporting

- full print-ready HTML report;
- pinned-only curated HTML report;
- Markdown;
- evidence CSV;
- JSON;
- GraphML.

The HTML report opens with a print flow so it can be saved as PDF without a server-side browser dependency.

## Architecture

```text
                     +--------------------------+
                     | public sources / exports |
                     +------------+-------------+
                                  |
                                  v
+----------------+      +---------+----------+
| React / Vite   | <--> | FastAPI            |
| Cytoscape      |      | normalization      |
| React Leaflet  |      | correlation        |
+----------------+      | analysis            |
                        +---------+----------+
                                  |
                    +-------------+-------------+
                    |                           |
                    v                           v
             SQLite case store          adapter boundary
             evidence + audit          external OSINT tools
```

Read:

- [Architecture](docs/ARCHITECTURE.md)
- [Methodology](docs/METHODOLOGY.md)
- [Tool strategy](docs/TOOLS.md)
- [Import schemas](docs/IMPORT_SCHEMA.md)
- [Case playbooks](docs/CASE_PLAYBOOKS.md)
- [Feature matrix](docs/FEATURE_MATRIX.md)

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- UI: http://localhost:5173
- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs

### Development

API:

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

Tests:

```bash
make test
```

## Typical workflow

1. Create a case with a clear intelligence question.
2. Run built-in public sources for a domain, URL or public IP.
3. Import tool output when relevant.
4. Review the graph instead of accepting correlations blindly.
5. Mark relationships confirmed/rejected/needs-review.
6. Build hypotheses and record counterpoints.
7. Use the timeline and coarse map to add context.
8. Snapshot important evidence.
9. Pin the items that should appear in the final report.
10. Export the full or curated report.

## Correlation policy

Weak indicators:

- similar username;
- similar display name;
- similar biography text.

Stronger indicators:

- shared externally controlled domain;
- reused public media hash;
- multiple independent sources;
- measurable temporal synchronization;
- explicit infrastructure relationships in machine-readable source output.

A similar username alone never becomes an identity verdict.

## Scope

VIGIL is suitable for:

- brand impersonation;
- public-account verification;
- CTI and defensive research;
- misinformation/coordinated-behavior analysis;
- public infrastructure research;
- due diligence based on lawful public sources;
- academic/journalistic verification workflows.

See [SECURITY.md](SECURITY.md) for the responsible-use policy.
