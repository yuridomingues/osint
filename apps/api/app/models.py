from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class TargetType(StrEnum):
    DOMAIN = "domain"
    ORGANIZATION = "organization"
    PUBLIC_ACCOUNT = "public_account"
    URL = "url"
    IP = "ip"


class CaseCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    target: str = Field(min_length=2, max_length=500)
    target_type: TargetType
    objective: str = Field(default="", max_length=1000)
    scope_acknowledged: bool

    @field_validator("target")
    @classmethod
    def normalize_target(cls, value: str) -> str:
        value = value.strip()
        return value.lstrip("@").lower() if "://" not in value else value


class Case(BaseModel):
    id: str
    name: str
    target: str
    target_type: TargetType
    objective: str
    created_at: str
    status: str = "ready"


class Entity(BaseModel):
    id: str
    case_id: str
    kind: str
    label: str
    canonical_key: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0, le=1)
    created_at: str = Field(default_factory=utc_now)


class Edge(BaseModel):
    id: str
    case_id: str
    source_id: str
    target_id: str
    relation: str
    confidence: float = Field(ge=0, le=1)
    rationale: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now)


class Evidence(BaseModel):
    id: str
    case_id: str
    source: str
    collector: str
    source_url: str | None = None
    excerpt: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    reliability: float = Field(default=0.6, ge=0, le=1)
    content_hash: str | None = None
    observed_at: str = Field(default_factory=utc_now)


class Finding(BaseModel):
    id: str
    case_id: str
    category: str
    severity: str
    title: str
    summary: str
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now)


class GraphResponse(BaseModel):
    case: Case
    entities: list[Entity]
    edges: list[Edge]
    evidence: list[Evidence]
    findings: list[Finding]


class PublicObservation(BaseModel):
    platform: str = Field(min_length=2, max_length=80)
    handle: str = Field(min_length=1, max_length=120)
    profile_url: str | None = None
    display_name: str | None = None
    bio: str | None = None
    external_urls: list[str] = Field(default_factory=list)
    media_hashes: list[str] = Field(default_factory=list)
    observed_at: str | None = None


class ObservationImport(BaseModel):
    observations: list[PublicObservation] = Field(min_length=1, max_length=500)


class ToolImport(BaseModel):
    tool: str = Field(pattern=r"^(sherlock_csv|maigret_json|subfinder_jsonl|amass_json|spiderfoot_csv)$")
    content: str = Field(min_length=1, max_length=5_000_000)


class PublicPost(BaseModel):
    platform: str = Field(min_length=2, max_length=80)
    author_handle: str = Field(min_length=1, max_length=120)
    url: str | None = None
    text: str = Field(min_length=1, max_length=10000)
    published_at: str


class PostImport(BaseModel):
    posts: list[PublicPost] = Field(min_length=1, max_length=1000)


class RunRequest(BaseModel):
    modules: list[str] = Field(default_factory=list)


class RunResponse(BaseModel):
    case_id: str
    modules_run: list[str]
    entities_added: int
    evidence_added: int
    findings_added: int
    warnings: list[str] = Field(default_factory=list)


class ImpersonationSignals(BaseModel):
    handle_similarity: float = Field(default=0, ge=0, le=1)
    display_name_similarity: float = Field(default=0, ge=0, le=1)
    reused_visual_identity: bool = False
    official_link_reuse: bool = False
    suspicious_external_domain: bool = False
    sparse_profile: bool = False
    synchronized_activity: bool = False


class Assessment(BaseModel):
    score: float
    level: str
    reasons: list[str]


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=20000)
    entity_ids: list[str] = Field(default_factory=list, max_length=100)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=30)


class Note(BaseModel):
    id: str
    case_id: str
    body: str
    entity_ids: list[str]
    evidence_ids: list[str]
    tags: list[str]
    created_at: str
    updated_at: str


class HypothesisStatus(StrEnum):
    OPEN = "open"
    SUPPORTED = "supported"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class HypothesisCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    statement: str = Field(min_length=3, max_length=5000)
    status: HypothesisStatus = HypothesisStatus.OPEN
    confidence: float = Field(default=0.5, ge=0, le=1)
    entity_ids: list[str] = Field(default_factory=list, max_length=100)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    counterpoints: list[str] = Field(default_factory=list, max_length=50)


class HypothesisUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    statement: str | None = Field(default=None, min_length=3, max_length=5000)
    status: HypothesisStatus | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    entity_ids: list[str] | None = None
    evidence_ids: list[str] | None = None
    counterpoints: list[str] | None = None


class Hypothesis(BaseModel):
    id: str
    case_id: str
    title: str
    statement: str
    status: HypothesisStatus
    confidence: float
    entity_ids: list[str]
    evidence_ids: list[str]
    counterpoints: list[str]
    created_at: str
    updated_at: str


class TimelineEventCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=5000)
    event_at: str
    source_url: str | None = None
    entity_ids: list[str] = Field(default_factory=list, max_length=100)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    category: str = Field(default="analyst", max_length=80)


class TimelineEvent(BaseModel):
    id: str
    case_id: str
    title: str
    description: str
    event_at: str
    source_url: str | None
    entity_ids: list[str]
    evidence_ids: list[str]
    category: str
    created_at: str


class GeoObservationCreate(BaseModel):
    label: str = Field(min_length=2, max_length=200)
    city: str = Field(default="", max_length=120)
    region: str = Field(default="", max_length=120)
    country: str = Field(default="", max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    source_url: str | None = None
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    entity_ids: list[str] = Field(default_factory=list, max_length=100)
    category: str = Field(default="public-context", max_length=80)

    @field_validator("latitude", "longitude")
    @classmethod
    def coarse_coordinates(cls, value: float) -> float:
        # City-level precision only. VIGIL is not designed for precise-person tracking.
        return round(value, 2)


class GeoObservation(BaseModel):
    id: str
    case_id: str
    label: str
    city: str
    region: str
    country: str
    latitude: float
    longitude: float
    source_url: str | None
    evidence_ids: list[str]
    entity_ids: list[str]
    category: str
    created_at: str


class PinCreate(BaseModel):
    object_type: Literal["entity", "edge", "evidence", "finding", "note", "hypothesis"]
    object_id: str
    label: str = Field(default="", max_length=200)


class Pin(BaseModel):
    id: str
    case_id: str
    object_type: str
    object_id: str
    label: str
    created_at: str


class SavedViewCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    filters: dict[str, Any] = Field(default_factory=dict)
    layout: dict[str, Any] = Field(default_factory=dict)


class SavedView(BaseModel):
    id: str
    case_id: str
    name: str
    filters: dict[str, Any]
    layout: dict[str, Any]
    created_at: str


class RelationReviewCreate(BaseModel):
    state: Literal["confirmed", "rejected", "needs_review"]
    comment: str = Field(default="", max_length=2000)


class RelationReview(BaseModel):
    id: str
    case_id: str
    edge_id: str
    state: str
    comment: str
    created_at: str
    updated_at: str


class EntityClusterCreate(BaseModel):
    label: str = Field(min_length=2, max_length=200)
    entity_ids: list[str] = Field(min_length=2, max_length=100)
    rationale: str = Field(default="", max_length=2000)


class SnapshotCreate(BaseModel):
    evidence_id: str


class Snapshot(BaseModel):
    id: str
    case_id: str
    evidence_id: str
    payload: dict[str, Any]
    content_hash: str
    created_at: str


class AuditEntry(BaseModel):
    id: str
    case_id: str
    action: str
    object_type: str
    object_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class WorkspaceResponse(BaseModel):
    graph: GraphResponse
    notes: list[Note]
    hypotheses: list[Hypothesis]
    timeline: list[TimelineEvent]
    geo: list[GeoObservation]
    pins: list[Pin]
    saved_views: list[SavedView]
    relation_reviews: list[RelationReview]
    snapshots: list[Snapshot]
    audit: list[AuditEntry]
