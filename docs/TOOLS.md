# Tool landscape and integration strategy

VIGIL is an orchestration and analysis layer. It should not clone mature tools when a stable export or API exists.

## Integrated now

| Tool/source | VIGIL role | Integration |
|---|---|---|
| Certificate Transparency / crt.sh | public certificate names | built-in passive collector |
| RDAP | public domain registration metadata | built-in passive collector |
| Internet Archive CDX | public historical URL evidence | built-in passive collector |
| Sherlock | public username results | CSV import adapter |
| Maigret | public username results | JSON / NDJSON import adapter |
| Cytoscape.js | entity-link analysis | native UI graph |
| JSON / GraphML | portability | native export |

## Recommended adapters

These are the next integrations worth adding. They are intentionally adapters, not forks.

| Tool | Best use in VIGIL | Preferred integration |
|---|---|---|
| SpiderFoot | broad OSINT automation for organizational cases | structured export/API -> VIGIL entities/evidence |
| Maltego | mature link analysis and transform ecosystem | GraphML both directions; custom transform server later |
| OWASP Amass | organization-owned attack-surface mapping | import passive asset output |
| ProjectDiscovery Subfinder | passive hostname discovery | import normalized hostname output |
| theHarvester | organization/domain research | JSONL/SQLite export adapter with scope filtering |
| ExifTool | metadata from files supplied to a case | local worker; preserve original file hash |
| urlscan.io | public web observations | API enrichment adapter |
| VirusTotal | domain/URL reputation and relationships | API enrichment adapter |
| Shodan / Censys | internet-exposure context | API enrichment for organization/domain cases |
| OpenCTI | CTI knowledge graph | STIX 2.1 import/export |
| MISP | threat-intelligence exchange | MISP JSON/PyMISP adapter |

## Why not run every CLI directly from the API?

Executing every third-party project inside the same process creates dependency conflicts, makes upgrades dangerous, complicates licensing and destroys reproducibility.

The preferred architecture is:

```text
tool -> machine-readable export -> adapter -> normalized evidence -> graph
```

For long-running integrations, use an isolated worker/container per tool.

## Normalized public-account observation

```json
{
  "platform": "github",
  "handle": "example",
  "profile_url": "https://github.com/example",
  "display_name": "Example",
  "bio": "Public profile text",
  "external_urls": ["https://example.org"],
  "media_hashes": []
}
```

## Tool-selection rules

- Prefer a mature upstream project over a local reimplementation.
- Preserve original provider/source names in evidence.
- Never collapse "not found", "blocked", "rate limited" and "unknown" into the same state.
- Treat profile existence checks as leads, not identity proof.
- Keep paid API enrichments optional.
- Avoid scraping when an official/public machine-readable interface exists.
- Pin adapters to a tested output schema and include fixture tests.

## Planned priority

1. SpiderFoot structured import.
2. ExifTool local-file metadata worker.
3. STIX 2.1 / OpenCTI connector.
4. MISP event import/export.
5. Passive Amass/Subfinder result ingestion.
6. URL/domain enrichment providers.
7. Signed case bundles and reproducible collection manifests.
