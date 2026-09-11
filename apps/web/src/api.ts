export const API = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export type TargetType = "domain" | "organization" | "public_account" | "url" | "ip";
export type HypothesisStatus = "open" | "supported" | "rejected" | "inconclusive";
export type ReviewState = "confirmed" | "rejected" | "needs_review";

export type Case = {
  id: string;
  name: string;
  target: string;
  target_type: TargetType;
  objective: string;
  created_at: string;
  status: string;
};

export type Entity = {
  id: string;
  case_id: string;
  kind: string;
  label: string;
  canonical_key: string;
  properties: Record<string, unknown>;
  confidence: number;
  created_at: string;
};

export type Edge = {
  id: string;
  case_id: string;
  source_id: string;
  target_id: string;
  relation: string;
  confidence: number;
  rationale: string[];
  evidence_ids: string[];
  created_at: string;
};

export type Evidence = {
  id: string;
  case_id: string;
  source: string;
  collector: string;
  source_url?: string | null;
  excerpt: string;
  reliability: number;
  content_hash?: string | null;
  observed_at: string;
  metadata: Record<string, unknown>;
};

export type Finding = {
  id: string;
  case_id: string;
  category: string;
  severity: string;
  title: string;
  summary: string;
  confidence: number;
  evidence_ids: string[];
  created_at: string;
};

export type Graph = {
  case: Case;
  entities: Entity[];
  edges: Edge[];
  evidence: Evidence[];
  findings: Finding[];
};

export type Note = {
  id: string;
  case_id: string;
  body: string;
  entity_ids: string[];
  evidence_ids: string[];
  tags: string[];
  created_at: string;
  updated_at: string;
};

export type Hypothesis = {
  id: string;
  case_id: string;
  title: string;
  statement: string;
  status: HypothesisStatus;
  confidence: number;
  entity_ids: string[];
  evidence_ids: string[];
  counterpoints: string[];
  created_at: string;
  updated_at: string;
};

export type TimelineEvent = {
  id: string;
  case_id: string;
  title: string;
  description: string;
  event_at: string;
  source_url?: string | null;
  entity_ids: string[];
  evidence_ids: string[];
  category: string;
  created_at: string;
};

export type GeoObservation = {
  id: string;
  case_id: string;
  label: string;
  city: string;
  region: string;
  country: string;
  latitude: number;
  longitude: number;
  source_url?: string | null;
  evidence_ids: string[];
  entity_ids: string[];
  category: string;
  created_at: string;
};

export type Pin = {
  id: string;
  case_id: string;
  object_type: "entity" | "edge" | "evidence" | "finding" | "note" | "hypothesis";
  object_id: string;
  label: string;
  created_at: string;
};

export type SavedView = {
  id: string;
  case_id: string;
  name: string;
  filters: Record<string, unknown>;
  layout: Record<string, unknown>;
  created_at: string;
};

export type RelationReview = {
  id: string;
  case_id: string;
  edge_id: string;
  state: ReviewState;
  comment: string;
  created_at: string;
  updated_at: string;
};

export type Snapshot = {
  id: string;
  case_id: string;
  evidence_id: string;
  payload: Record<string, unknown>;
  content_hash: string;
  created_at: string;
};

export type AuditEntry = {
  id: string;
  case_id: string;
  action: string;
  object_type: string;
  object_id?: string | null;
  details: Record<string, unknown>;
  created_at: string;
};

export type Workspace = {
  graph: Graph;
  notes: Note[];
  hypotheses: Hypothesis[];
  timeline: TimelineEvent[];
  geo: GeoObservation[];
  pins: Pin[];
  saved_views: SavedView[];
  relation_reviews: RelationReview[];
  snapshots: Snapshot[];
  audit: AuditEntry[];
};

export type ModuleInfo = {
  id: string;
  name: string;
  mode: string;
  available: boolean;
  description?: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) }
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  cases: () => request<Case[]>("/cases"),
  graph: (id: string) => request<Graph>(`/cases/${id}`),
  workspace: (id: string) => request<Workspace>(`/cases/${id}/workspace`),
  modules: () => request<ModuleInfo[]>("/modules"),

  createCase: (payload: {
    name: string;
    target: string;
    target_type: TargetType;
    objective: string;
    scope_acknowledged: boolean;
  }) => request<Case>("/cases", { method: "POST", body: JSON.stringify(payload) }),

  runCase: (id: string, modules: string[] = []) => request(`/cases/${id}/run`, {
    method: "POST",
    body: JSON.stringify({ modules })
  }),

  importObservations: (id: string, observations: unknown[]) => request(`/cases/${id}/observations`, {
    method: "POST",
    body: JSON.stringify({ observations })
  }),

  importTool: (id: string, tool: "sherlock_csv" | "maigret_json" | "subfinder_jsonl" | "amass_json" | "spiderfoot_csv", content: string) => request(`/cases/${id}/tool-import`, {
    method: "POST",
    body: JSON.stringify({ tool, content })
  }),

  importPosts: (id: string, posts: unknown[]) => request(`/cases/${id}/posts`, {
    method: "POST",
    body: JSON.stringify({ posts })
  }),

  addNote: (id: string, payload: {
    body: string;
    entity_ids?: string[];
    evidence_ids?: string[];
    tags?: string[];
  }) => request<Note>(`/cases/${id}/notes`, {
    method: "POST",
    body: JSON.stringify(payload)
  }),

  deleteNote: (id: string, noteId: string) => request(`/cases/${id}/notes/${noteId}`, {
    method: "DELETE"
  }),

  addHypothesis: (id: string, payload: {
    title: string;
    statement: string;
    status?: HypothesisStatus;
    confidence?: number;
    entity_ids?: string[];
    evidence_ids?: string[];
    counterpoints?: string[];
  }) => request<Hypothesis>(`/cases/${id}/hypotheses`, {
    method: "POST",
    body: JSON.stringify(payload)
  }),

  updateHypothesis: (id: string, hypothesisId: string, payload: Partial<{
    title: string;
    statement: string;
    status: HypothesisStatus;
    confidence: number;
    entity_ids: string[];
    evidence_ids: string[];
    counterpoints: string[];
  }>) => request<Hypothesis>(`/cases/${id}/hypotheses/${hypothesisId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  }),

  addTimelineEvent: (id: string, payload: {
    title: string;
    description?: string;
    event_at: string;
    source_url?: string;
    entity_ids?: string[];
    evidence_ids?: string[];
    category?: string;
  }) => request<TimelineEvent>(`/cases/${id}/timeline`, {
    method: "POST",
    body: JSON.stringify(payload)
  }),

  generateTimeline: (id: string) => request(`/cases/${id}/timeline/generate`, {
    method: "POST"
  }),

  addGeo: (id: string, payload: {
    label: string;
    city?: string;
    region?: string;
    country?: string;
    latitude: number;
    longitude: number;
    source_url?: string;
    evidence_ids?: string[];
    entity_ids?: string[];
    category?: string;
  }) => request<GeoObservation>(`/cases/${id}/geo`, {
    method: "POST",
    body: JSON.stringify(payload)
  }),

  addPin: (id: string, payload: {
    object_type: Pin["object_type"];
    object_id: string;
    label?: string;
  }) => request<Pin>(`/cases/${id}/pins`, {
    method: "POST",
    body: JSON.stringify(payload)
  }),

  deletePin: (id: string, pinId: string) => request(`/cases/${id}/pins/${pinId}`, {
    method: "DELETE"
  }),

  saveView: (id: string, payload: {
    name: string;
    filters?: Record<string, unknown>;
    layout?: Record<string, unknown>;
  }) => request<SavedView>(`/cases/${id}/saved-views`, {
    method: "POST",
    body: JSON.stringify(payload)
  }),

  reviewEdge: (id: string, edgeId: string, payload: {
    state: ReviewState;
    comment?: string;
  }) => request<RelationReview>(`/cases/${id}/edges/${edgeId}/review`, {
    method: "PUT",
    body: JSON.stringify(payload)
  }),

  createCluster: (id: string, payload: {
    label: string;
    entity_ids: string[];
    rationale?: string;
  }) => request<Entity>(`/cases/${id}/clusters`, {
    method: "POST",
    body: JSON.stringify(payload)
  }),

  detachClusterMember: (id: string, clusterId: string, entityId: string) => request(
    `/cases/${id}/clusters/${clusterId}/members/${entityId}`,
    { method: "DELETE" }
  ),

  snapshotEvidence: (id: string, evidenceId: string) => request<Snapshot>(
    `/cases/${id}/snapshots`,
    { method: "POST", body: JSON.stringify({ evidence_id: evidenceId }) }
  ),

  exportUrl: (id: string, format: "json" | "graphml") =>
    `${API}/cases/${id}/export?format=${format}`,

  reportUrl: (id: string, format: "html" | "md" | "csv", curatedOnly = false) =>
    `${API}/cases/${id}/report?format=${format}&curated_only=${curatedOnly}`
};
