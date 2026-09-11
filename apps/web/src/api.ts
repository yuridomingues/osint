export const API = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export type TargetType = "domain" | "organization" | "public_account";

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
};

export type Edge = {
  id: string;
  source_id: string;
  target_id: string;
  relation: string;
  confidence: number;
  rationale: string[];
  evidence_ids: string[];
};

export type Evidence = {
  id: string;
  source: string;
  collector: string;
  source_url?: string;
  excerpt: string;
  reliability: number;
  observed_at: string;
  metadata: Record<string, unknown>;
};

export type Finding = {
  id: string;
  category: string;
  severity: string;
  title: string;
  summary: string;
  confidence: number;
};

export type Graph = {
  case: Case;
  entities: Entity[];
  edges: Edge[];
  evidence: Evidence[];
  findings: Finding[];
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
  modules: () => request<Array<{id:string;name:string;mode:string;available:boolean}>>("/modules"),
  createCase: (payload: {
    name: string; target: string; target_type: TargetType; objective: string; scope_acknowledged: boolean;
  }) => request<Case>("/cases", { method: "POST", body: JSON.stringify(payload) }),
  runCase: (id: string) => request(`/cases/${id}/run`, {
    method: "POST", body: JSON.stringify({ modules: [] })
  }),
  importObservations: (id: string, observations: unknown[]) => request(`/cases/${id}/observations`, {
    method: "POST", body: JSON.stringify({ observations })
  }),
  exportUrl: (id: string, format: "json" | "graphml") => `${API}/cases/${id}/export?format=${format}`
};
