from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
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


class CaseCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    target: str = Field(min_length=2, max_length=253)
    target_type: TargetType
    objective: str = Field(default="", max_length=500)
    scope_acknowledged: bool

    @field_validator("target")
    @classmethod
    def normalize_target(cls, value: str) -> str:
        return value.strip().lstrip("@").lower()


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
    tool: str = Field(pattern=r"^(sherlock_csv|maigret_json)$")
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
