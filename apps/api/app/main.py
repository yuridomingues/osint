from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from .analysis import assess_impersonation
from .collectors import collect_domain_public_sources
from .coordination import analyze_public_posts
from .correlation import import_public_observations
from .exporters import as_graphml, as_json
from .models import (
    Assessment,
    Case,
    CaseCreate,
    GraphResponse,
    ImpersonationSignals,
    ObservationImport,
    PostImport,
    RunRequest,
    RunResponse,
    TargetType,
    ToolImport,
)
from .store import Store
from .tool_imports import import_tool_export

app = FastAPI(
    title="VIGIL OSINT API",
    version="0.1.0",
    description="Public-source investigation, provenance and entity-correlation workbench.",
)

origins = [
    value.strip()
    for value in os.getenv("VIGIL_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if value.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = Store()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "vigil-osint-api"}


@app.get("/modules")
def modules() -> list[dict]:
    return [
        {
            "id": "public-domain",
            "name": "Certificate Transparency + RDAP + Wayback",
            "mode": "passive",
            "available": True,
            "description": "Built-in public domain intelligence.",
        },
        {
            "id": "sherlock",
            "name": "Sherlock",
            "mode": "import",
            "available": True,
            "description": "CSV export normalization for public-account evidence.",
        },
        {
            "id": "maigret",
            "name": "Maigret",
            "mode": "import",
            "available": True,
            "description": "JSON/NDJSON export normalization for public-account evidence.",
        },
        {
            "id": "public-observations",
            "name": "Generic public observations",
            "mode": "import",
            "available": True,
            "description": "Normalized schema for outputs from other tools and manual research.",
        },
        {
            "id": "coordination",
            "name": "Coordinated behavior",
            "mode": "analysis",
            "available": True,
            "description": "Detects synchronized identical public content while preserving uncertainty.",
        },
        {
            "id": "impersonation",
            "name": "Impersonation scoring",
            "mode": "analysis",
            "available": True,
            "description": "Explainable multi-signal fake/impersonation assessment.",
        },
        {
            "id": "spiderfoot",
            "name": "SpiderFoot",
            "mode": "adapter",
            "available": False,
            "description": "Planned normalized export adapter.",
        },
        {
            "id": "maltego",
            "name": "Maltego",
            "mode": "graph",
            "available": True,
            "description": "GraphML export is compatible with graph-analysis workflows.",
        },
        {
            "id": "opencti-misp",
            "name": "OpenCTI / MISP",
            "mode": "cti",
            "available": False,
            "description": "STIX/MISP adapters planned for threat-intelligence exchange.",
        },
        {
            "id": "exiftool",
            "name": "ExifTool",
            "mode": "metadata",
            "available": False,
            "description": "Local-file metadata adapter planned.",
        },
        {
            "id": "graph-export",
            "name": "JSON / GraphML export",
            "mode": "export",
            "available": True,
            "description": "Portable evidence graph for other analysis tools.",
        },
    ]


@app.post("/cases", response_model=Case)
def create_case(payload: CaseCreate) -> Case:
    if not payload.scope_acknowledged:
        raise HTTPException(
            400,
            "Confirme que o caso usa fontes públicas e possui finalidade legítima.",
        )
    return store.create_case(payload)


@app.get("/cases", response_model=list[Case])
def list_cases() -> list[Case]:
    return store.list_cases()


@app.get("/cases/{case_id}", response_model=GraphResponse)
def case_graph(case_id: str) -> GraphResponse:
    graph = store.graph(case_id)
    if not graph:
        raise HTTPException(404, "Case not found")
    return graph


@app.post("/cases/{case_id}/run", response_model=RunResponse)
async def run_case(case_id: str, payload: RunRequest) -> RunResponse:
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")

    store.set_status(case_id, "running")
    entities_added = evidence_added = findings_added = 0
    warnings: list[str] = []
    modules_run: list[str] = []

    try:
        requested = set(payload.modules)
        if case.target_type in {TargetType.DOMAIN, TargetType.ORGANIZATION} and (
            not requested or "public-domain" in requested
        ):
            a, b, c, w = await collect_domain_public_sources(store, case_id, case.target)
            entities_added += a
            evidence_added += b
            findings_added += c
            warnings.extend(w)
            modules_run.append("public-domain")

        if case.target_type == TargetType.PUBLIC_ACCOUNT:
            warnings.append(
                "Contas públicas são correlacionadas a partir de observações importadas; "
                "não há varredura automática de pessoas."
            )
    finally:
        store.set_status(case_id, "ready")

    return RunResponse(
        case_id=case_id,
        modules_run=modules_run,
        entities_added=entities_added,
        evidence_added=evidence_added,
        findings_added=findings_added,
        warnings=warnings,
    )


@app.post("/cases/{case_id}/observations")
def import_observations(case_id: str, payload: ObservationImport) -> dict:
    if not store.get_case(case_id):
        raise HTTPException(404, "Case not found")
    entities, evidence = import_public_observations(store, case_id, payload.observations)
    return {"entities_added": entities, "evidence_added": evidence}


@app.post("/cases/{case_id}/tool-import")
def tool_import(case_id: str, payload: ToolImport) -> dict:
    if not store.get_case(case_id):
        raise HTTPException(404, "Case not found")
    try:
        return import_tool_export(store, case_id, payload.tool, payload.content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/cases/{case_id}/posts")
def import_posts(case_id: str, payload: PostImport) -> dict:
    if not store.get_case(case_id):
        raise HTTPException(404, "Case not found")
    return analyze_public_posts(store, case_id, payload.posts)


@app.post("/analysis/impersonation", response_model=Assessment)
def impersonation(payload: ImpersonationSignals) -> Assessment:
    return assess_impersonation(payload)


@app.get("/cases/{case_id}/export")
def export_case(case_id: str, format: str = "json") -> Response:
    graph = store.graph(case_id)
    if not graph:
        raise HTTPException(404, "Case not found")

    if format == "graphml":
        return Response(as_graphml(graph), media_type="application/graphml+xml")
    if format == "json":
        return Response(as_json(graph), media_type="application/json")
    raise HTTPException(400, "Supported formats: json, graphml")
