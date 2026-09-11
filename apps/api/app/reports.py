from __future__ import annotations

import csv
import html
import io
from datetime import datetime, timezone

from .models import WorkspaceResponse


def _esc(value: object) -> str:
    return html.escape(str(value or ""))


def report_markdown(workspace: WorkspaceResponse, curated_only: bool = False) -> str:
    graph = workspace.graph
    pinned = {(pin.object_type, pin.object_id) for pin in workspace.pins}

    findings = graph.findings
    evidence = graph.evidence
    entities = graph.entities
    hypotheses = workspace.hypotheses

    if curated_only and pinned:
        findings = [item for item in findings if ("finding", item.id) in pinned]
        evidence = [item for item in evidence if ("evidence", item.id) in pinned]
        entities = [item for item in entities if ("entity", item.id) in pinned]
        hypotheses = [item for item in hypotheses if ("hypothesis", item.id) in pinned]

    lines = [
        f"# {graph.case.name}",
        "",
        f"Target: {graph.case.target}",
        f"Type: {graph.case.target_type.value}",
        f"Objective: {graph.case.objective or 'Not specified'}",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Executive summary",
        "",
        f"- {len(entities)} entities in scope",
        f"- {len(graph.edges)} relationships",
        f"- {len(evidence)} evidence records",
        f"- {len(findings)} findings",
        f"- {len(hypotheses)} analyst hypotheses",
        "",
    ]

    if findings:
        lines += ["## Findings", ""]
        for item in findings:
            lines += [
                f"### {item.title}",
                f"- Severity: {item.severity}",
                f"- Confidence: {round(item.confidence * 100)}%",
                f"- Category: {item.category}",
                "",
                item.summary,
                "",
            ]

    if hypotheses:
        lines += ["## Hypotheses", ""]
        for item in hypotheses:
            lines += [
                f"### {item.title}",
                f"- Status: {item.status.value}",
                f"- Confidence: {round(item.confidence * 100)}%",
                "",
                item.statement,
                "",
            ]
            if item.counterpoints:
                lines += ["Counterpoints:"]
                lines += [f"- {point}" for point in item.counterpoints]
                lines.append("")

    if entities:
        lines += ["## Entities", ""]
        for item in entities:
            lines.append(
                f"- {item.label} · {item.kind} · confidence {round(item.confidence * 100)}%"
            )
        lines.append("")

    if evidence:
        lines += ["## Evidence ledger", ""]
        for item in evidence:
            lines += [
                f"### {item.source}",
                f"- Collector: {item.collector}",
                f"- Observed: {item.observed_at}",
                f"- Reliability: {round(item.reliability * 100)}%",
                f"- Hash: {item.content_hash or 'n/a'}",
            ]
            if item.source_url:
                lines.append(f"- Source URL: {item.source_url}")
            if item.excerpt:
                lines += ["", item.excerpt]
            lines.append("")

    if workspace.timeline:
        lines += ["## Timeline", ""]
        for event in workspace.timeline:
            lines.append(f"- {event.event_at} — {event.title}: {event.description}")
        lines.append("")

    if workspace.geo:
        lines += ["## Geospatial context", ""]
        for point in workspace.geo:
            place = ", ".join(x for x in (point.city, point.region, point.country) if x)
            lines.append(f"- {point.label} — {place or 'coarse public context'}")
        lines.append("")

    lines += [
        "## Methodology note",
        "",
        "VIGIL separates source observations from analyst assessments. Correlation scores and coordination indicators are leads for review, not automatic identity or attribution verdicts.",
        "",
    ]
    return "\n".join(lines)


def report_html(workspace: WorkspaceResponse, curated_only: bool = False) -> str:
    markdown = report_markdown(workspace, curated_only)
    blocks: list[str] = []
    in_list = False

    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.startswith("# "):
            if in_list:
                blocks.append("</ul>")
                in_list = False
            blocks.append(f"<h1>{_esc(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_list:
                blocks.append("</ul>")
                in_list = False
            blocks.append(f"<h2>{_esc(line[3:])}</h2>")
        elif line.startswith("### "):
            if in_list:
                blocks.append("</ul>")
                in_list = False
            blocks.append(f"<h3>{_esc(line[4:])}</h3>")
        elif line.startswith("- "):
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append(f"<li>{_esc(line[2:])}</li>")
        elif not line:
            if in_list:
                blocks.append("</ul>")
                in_list = False
        else:
            if in_list:
                blocks.append("</ul>")
                in_list = False
            blocks.append(f"<p>{_esc(line)}</p>")

    if in_list:
        blocks.append("</ul>")

    body = "\n".join(blocks)
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{_esc(workspace.graph.case.name)} · VIGIL report</title>
<style>
@page {{ margin: 18mm; }}
body {{ font-family: Inter, Arial, sans-serif; color:#172019; max-width:900px; margin:auto; line-height:1.55; }}
header {{ border-bottom:3px solid #172019; margin-bottom:28px; padding-bottom:12px; }}
.brand {{ font-size:12px; letter-spacing:.16em; font-weight:700; }}
h1 {{ font-size:34px; letter-spacing:-.03em; }}
h2 {{ margin-top:34px; border-bottom:1px solid #cad3cd; padding-bottom:7px; }}
h3 {{ margin-top:24px; }}
p,li {{ font-size:12px; }}
footer {{ margin-top:50px; border-top:1px solid #cad3cd; padding-top:10px; font-size:9px; color:#68766d; }}
@media print {{ .no-print {{ display:none; }} body {{ max-width:none; }} }}
</style>
</head>
<body>
<header><div class="brand">VIGIL · OSINT WORKBENCH</div></header>
{body}
<footer>Generated from a provenance-first VIGIL case. Review original sources before operational use.</footer>
<script>window.addEventListener('load',()=>setTimeout(()=>window.print(),250));</script>
</body>
</html>"""


def evidence_csv(workspace: WorkspaceResponse) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "source", "collector", "source_url", "observed_at",
        "reliability", "content_hash", "excerpt",
    ])
    for item in workspace.graph.evidence:
        writer.writerow([
            item.id,
            item.source,
            item.collector,
            item.source_url or "",
            item.observed_at,
            item.reliability,
            item.content_hash or "",
            item.excerpt,
        ])
    return output.getvalue()
