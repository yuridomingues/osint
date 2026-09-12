from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from .analysis import assess_impersonation
from .collectors import collect_domain_public_sources
from .coordination import analyze_public_posts
from .correlation import import_public_observations
from .exporters import as_graphml, as_json
from .identity_discovery import collect_public_identity_discovery
from .image_evidence import attach_image_evidence
from .models import (
    Assessment,
    Case,
    CaseCreate,
    Entity,
    EntityClusterCreate,
    GeoObservation,
    GeoObservationCreate,
    GraphResponse,
    Hypothesis,
    HypothesisCreate,
    HypothesisUpdate,
    ImpersonationSignals,
    ImageEvidenceImport,
    Note,
    NoteCreate,
    ObservationImport,
    Pin,
    PinCreate,
    PostImport,
    RelationReview,
    RelationReviewCreate,
    RunRequest,
    RunResponse,
    SavedView,
    SavedViewCreate,
    Snapshot,
    SnapshotCreate,
    TargetType,
    TimelineEvent,
    TimelineEventCreate,
    ToolImport,
    WorkspaceResponse,
)
from .network_collectors import collect_ip_public_sources, collect_url_public_sources
from .reports import evidence_csv, report_html, report_markdown
from .store import Store
from .tool_imports import import_tool_export
from .workspace import (
    auto_timeline_from_evidence,
    create_cluster,
    create_geo_observation,
    create_hypothesis,
    create_note,
    create_pin,
    create_saved_view,
    create_snapshot,
    create_timeline_event,
    delete_note,
    delete_pin,
    detach_cluster_member,
    get_workspace,
    review_relation,
    update_hypothesis,
)

app = FastAPI(
    title="VIGIL OSINT API",
    version="0.4.0",
    description="Public-source investigation, provenance, link analysis and analyst-workspace API.",
)

default_origins = "*" if os.getenv("VERCEL") else "http://localhost:5173"
origins = [
    value.strip()
    for value in os.getenv("VIGIL_ALLOWED_ORIGINS", default_origins).split(",")
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


def require_case(case_id: str) -> Case:
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "vigil-osint-api",
        "version": "0.4.0",
        "environment": "vercel-test" if os.getenv("VERCEL") else "local",
        "persistence": "ephemeral" if os.getenv("VERCEL") else "sqlite",
    }


@app.get("/modules")
def modules() -> list[dict]:
    return [
        {
            "id": "public-domain",
            "name": "Certificate Transparency + RDAP + Wayback",
            "mode": "passive",
            "available": True,
            "description": "Passive domain intelligence from public registries and archives.",
        },
        {
            "id": "public-ip",
            "name": "IP allocation intelligence",
            "mode": "passive",
            "available": True,
            "description": "Public RDAP allocation context; no precise-person geolocation.",
        },
        {
            "id": "public-url",
            "name": "URL archive intelligence",
            "mode": "passive",
            "available": True,
            "description": "URL/domain normalization plus Internet Archive history.",
        },
        {
            "id": "identity-discovery",
            "name": "Public identity discovery",
            "mode": "passive",
            "available": True,
            "description": "Different-handle public-profile discovery using web search, public metadata, explicit backlinks and GitHub history.",
        },
        {
            "id": "image-evidence",
            "name": "Image evidence",
            "mode": "analysis",
            "available": True,
            "description": "Local SHA-256, aHash/dHash, EXIF and optional C2PA analysis without facial identification.",
        },
        {
            "id": "reverse-image-tineye",
            "name": "TinEye reverse image",
            "mode": "enrichment",
            "available": bool(os.getenv("TINEYE_API_KEY", "").strip()),
            "description": "Optional same/modified-image web search. Requires TINEYE_API_KEY; this is not face recognition.",
        },
        {
            "id": "sherlock",
            "name": "Sherlock",
            "mode": "import",
            "available": True,
            "description": "CSV export normalization for public-account observations.",
        },
        {
            "id": "maigret",
            "name": "Maigret",
            "mode": "import",
            "available": True,
            "description": "JSON/NDJSON export normalization for public-account observations.",
        },
        {
            "id": "public-observations",
            "name": "Generic public observations",
            "mode": "import",
            "available": True,
            "description": "Normalized schema for other tools and manual research.",
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
            "id": "analyst-workspace",
            "name": "Analyst workspace",
            "mode": "analysis",
            "available": True,
            "description": "Notes, hypotheses, pins, relation review, timeline, saved views and audit.",
        },
        {
            "id": "reports",
            "name": "Curated reports",
            "mode": "export",
            "available": True,
            "description": "Print-ready HTML, Markdown, evidence CSV, JSON and GraphML.",
        },
        {
            "id": "subfinder",
            "name": "ProjectDiscovery Subfinder",
            "mode": "import",
            "available": True,
            "description": "JSONL passive-hostname export adapter for organizational cases.",
        },
        {
            "id": "amass",
            "name": "OWASP Amass",
            "mode": "import",
            "available": True,
            "description": "JSON passive asset graph adapter for organizational cases.",
        },
        {
            "id": "spiderfoot",
            "name": "SpiderFoot",
            "mode": "import",
            "available": True,
            "description": "CSV infrastructure-result adapter with person/contact event types excluded.",
        },
        {
            "id": "opencti-misp",
            "name": "OpenCTI / MISP",
            "mode": "cti",
            "available": False,
            "description": "STIX/MISP exchange adapter planned.",
        },
        {
            "id": "graph-export",
            "name": "JSON / GraphML export",
            "mode": "export",
            "available": True,
            "description": "Portable evidence graph for external analysis tools.",
        },
    ]


@app.post("/cases", response_model=Case)
def create_case(payload: CaseCreate) -> Case:
    if not payload.scope_acknowledged:
        raise HTTPException(
            400,
            "Confirme que o case usa fontes públicas e possui finalidade legítima.",
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


@app.get("/cases/{case_id}/workspace", response_model=WorkspaceResponse)
def case_workspace(case_id: str) -> WorkspaceResponse:
    workspace = get_workspace(store, case_id)
    if not workspace:
        raise HTTPException(404, "Case not found")
    return workspace


@app.post("/cases/{case_id}/run", response_model=RunResponse)
async def run_case(case_id: str, payload: RunRequest) -> RunResponse:
    case = require_case(case_id)

    store.set_status(case_id, "running")
    entities_added = evidence_added = findings_added = 0
    warnings: list[str] = []
    modules_run: list[str] = []

    try:
        requested = set(payload.modules)
        run_default = not requested

        if case.target_type in {TargetType.DOMAIN, TargetType.ORGANIZATION} and (
            run_default or "public-domain" in requested
        ):
            a, b, c, w = await collect_domain_public_sources(store, case_id, case.target)
            entities_added += a
            evidence_added += b
            findings_added += c
            warnings.extend(w)
            modules_run.append("public-domain")

        if case.target_type == TargetType.IP and (run_default or "public-ip" in requested):
            a, b, c, w = await collect_ip_public_sources(store, case_id, case.target)
            entities_added += a
            evidence_added += b
            findings_added += c
            warnings.extend(w)
            modules_run.append("public-ip")

        if case.target_type == TargetType.URL and (run_default or "public-url" in requested):
            a, b, c, w = await collect_url_public_sources(store, case_id, case.target)
            entities_added += a
            evidence_added += b
            findings_added += c
            warnings.extend(w)
            modules_run.append("public-url")

        if case.target_type == TargetType.PUBLIC_ACCOUNT and (
            run_default or "identity-discovery" in requested
        ):
            a, b, c, w = await collect_public_identity_discovery(
                store, case_id, case.target
            )
            entities_added += a
            evidence_added += b
            findings_added += c
            warnings.extend(w)
            modules_run.append("identity-discovery")
    finally:
        store.set_status(case_id, "ready")

    if evidence_added:
        auto_timeline_from_evidence(store, case_id)

    store.audit(
        case_id,
        "collection.completed",
        "case",
        case_id,
        {
            "modules": modules_run,
            "entities_added": entities_added,
            "evidence_added": evidence_added,
            "findings_added": findings_added,
        },
    )

    return RunResponse(
        case_id=case_id,
        modules_run=modules_run,
        entities_added=entities_added,
        evidence_added=evidence_added,
        findings_added=findings_added,
        warnings=warnings,
    )


@app.post("/cases/{case_id}/images")
async def add_image_evidence(case_id: str, payload: ImageEvidenceImport) -> dict:
    require_case(case_id)
    try:
        result = await attach_image_evidence(store, case_id, payload)
        auto_timeline_from_evidence(store, case_id)
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/cases/{case_id}/observations")
def import_observations(case_id: str, payload: ObservationImport) -> dict:
    require_case(case_id)
    entities, evidence = import_public_observations(store, case_id, payload.observations)
    auto_timeline_from_evidence(store, case_id)
    store.audit(
        case_id,
        "observations.imported",
        "case",
        case_id,
        {"records": len(payload.observations), "entities_added": entities, "evidence_added": evidence},
    )
    return {"entities_added": entities, "evidence_added": evidence}


@app.post("/cases/{case_id}/tool-import")
def tool_import(case_id: str, payload: ToolImport) -> dict:
    case = require_case(case_id)
    infrastructure_tools = {"subfinder_jsonl", "amass_json", "spiderfoot_csv"}
    if payload.tool in infrastructure_tools and case.target_type not in {
        TargetType.DOMAIN,
        TargetType.ORGANIZATION,
    }:
        raise HTTPException(
            400,
            "Infrastructure adapters are limited to domain/organization cases.",
        )
    try:
        result = import_tool_export(store, case_id, payload.tool, payload.content)
        auto_timeline_from_evidence(store, case_id)
        store.audit(case_id, "tool.imported", "case", case_id, result)
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/cases/{case_id}/posts")
def import_posts(case_id: str, payload: PostImport) -> dict:
    require_case(case_id)
    result = analyze_public_posts(store, case_id, payload.posts)
    auto_timeline_from_evidence(store, case_id)
    store.audit(case_id, "posts.imported", "case", case_id, {"records": len(payload.posts), **result})
    return result


@app.post("/analysis/impersonation", response_model=Assessment)
def impersonation(payload: ImpersonationSignals) -> Assessment:
    return assess_impersonation(payload)


@app.post("/cases/{case_id}/notes", response_model=Note)
def add_note(case_id: str, payload: NoteCreate) -> Note:
    require_case(case_id)
    return create_note(store, case_id, payload)


@app.delete("/cases/{case_id}/notes/{note_id}")
def remove_note(case_id: str, note_id: str) -> dict:
    require_case(case_id)
    if not delete_note(store, case_id, note_id):
        raise HTTPException(404, "Note not found")
    return {"deleted": True}


@app.post("/cases/{case_id}/hypotheses", response_model=Hypothesis)
def add_hypothesis(case_id: str, payload: HypothesisCreate) -> Hypothesis:
    require_case(case_id)
    return create_hypothesis(store, case_id, payload)


@app.patch("/cases/{case_id}/hypotheses/{hypothesis_id}", response_model=Hypothesis)
def edit_hypothesis(
    case_id: str,
    hypothesis_id: str,
    payload: HypothesisUpdate,
) -> Hypothesis:
    require_case(case_id)
    result = update_hypothesis(store, case_id, hypothesis_id, payload)
    if not result:
        raise HTTPException(404, "Hypothesis not found")
    return result


@app.post("/cases/{case_id}/timeline", response_model=TimelineEvent)
def add_timeline_event(case_id: str, payload: TimelineEventCreate) -> TimelineEvent:
    require_case(case_id)
    return create_timeline_event(store, case_id, payload)


@app.post("/cases/{case_id}/timeline/generate")
def generate_timeline(case_id: str) -> dict:
    require_case(case_id)
    return {"events_added": auto_timeline_from_evidence(store, case_id)}


@app.post("/cases/{case_id}/geo", response_model=GeoObservation)
def add_geo(case_id: str, payload: GeoObservationCreate) -> GeoObservation:
    require_case(case_id)
    return create_geo_observation(store, case_id, payload)


@app.post("/cases/{case_id}/pins", response_model=Pin)
def add_pin(case_id: str, payload: PinCreate) -> Pin:
    require_case(case_id)
    return create_pin(store, case_id, payload)


@app.delete("/cases/{case_id}/pins/{pin_id}")
def remove_pin(case_id: str, pin_id: str) -> dict:
    require_case(case_id)
    if not delete_pin(store, case_id, pin_id):
        raise HTTPException(404, "Pin not found")
    return {"deleted": True}


@app.post("/cases/{case_id}/saved-views", response_model=SavedView)
def add_saved_view(case_id: str, payload: SavedViewCreate) -> SavedView:
    require_case(case_id)
    return create_saved_view(store, case_id, payload)


@app.put("/cases/{case_id}/edges/{edge_id}/review", response_model=RelationReview)
def put_relation_review(
    case_id: str,
    edge_id: str,
    payload: RelationReviewCreate,
) -> RelationReview:
    graph = store.graph(case_id)
    if not graph:
        raise HTTPException(404, "Case not found")
    if edge_id not in {edge.id for edge in graph.edges}:
        raise HTTPException(404, "Edge not found")
    return review_relation(store, case_id, edge_id, payload)


@app.post("/cases/{case_id}/clusters", response_model=Entity)
def add_cluster(case_id: str, payload: EntityClusterCreate) -> Entity:
    require_case(case_id)
    try:
        return create_cluster(store, case_id, payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/cases/{case_id}/clusters/{cluster_id}/members/{entity_id}")
def remove_cluster_member(case_id: str, cluster_id: str, entity_id: str) -> dict:
    require_case(case_id)
    if not detach_cluster_member(store, case_id, cluster_id, entity_id):
        raise HTTPException(404, "Cluster membership not found")
    return {"detached": True}


@app.post("/cases/{case_id}/snapshots", response_model=Snapshot)
def add_snapshot(case_id: str, payload: SnapshotCreate) -> Snapshot:
    require_case(case_id)
    try:
        return create_snapshot(store, case_id, payload)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/cases/{case_id}/report")
def report_case(
    case_id: str,
    format: str = "html",
    curated_only: bool = False,
) -> Response:
    workspace = get_workspace(store, case_id)
    if not workspace:
        raise HTTPException(404, "Case not found")

    if format == "html":
        return Response(report_html(workspace, curated_only), media_type="text/html")
    if format == "md":
        return Response(report_markdown(workspace, curated_only), media_type="text/markdown")
    if format == "csv":
        return Response(evidence_csv(workspace), media_type="text/csv")
    raise HTTPException(400, "Supported report formats: html, md, csv")


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
