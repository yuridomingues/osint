import { useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, Boxes, CalendarClock, ChevronRight, CircleDot,
  Database, FileSearch, FileText, Globe2, Lightbulb, ListChecks, Map,
  Network, Play, Plus, RefreshCw, Search, ShieldCheck, X
} from "lucide-react";
import { api, Case, ModuleInfo, TargetType, Workspace } from "./api";
import AnalysisPanel from "./components/AnalysisPanel";
import EvidencePanel from "./components/EvidencePanel";
import GraphCanvas from "./components/GraphCanvas";
import ImportPanel from "./components/ImportPanel";
import MapPanel from "./components/MapPanel";
import ModulesPanel from "./components/ModulesPanel";
import ReportPanel from "./components/ReportPanel";
import TimelinePanel from "./components/TimelinePanel";

type Tab =
  | "graph"
  | "evidence"
  | "findings"
  | "timeline"
  | "map"
  | "analysis"
  | "report"
  | "modules"
  | "audit";

function guessTargetType(value: string): TargetType {
  const target = value.trim();
  if (/^https?:\/\//i.test(target)) return "url";
  if (/^(?:\d{1,3}\.){3}\d{1,3}$/.test(target) || target.includes(":")) return "ip";
  if (target.startsWith("@")) return "public_account";
  if (/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(target)) return "domain";
  return "public_account";
}

function NewCaseModal({
  onClose,
  onCreated
}: {
  onClose: () => void;
  onCreated: (item: Case) => void;
}) {
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [targetType, setTargetType] = useState<TargetType>("domain");
  const [objective, setObjective] = useState("");
  const [ack, setAck] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function updateTarget(value: string) {
    setTarget(value);
    if (value.trim()) setTargetType(guessTargetType(value));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const created = await api.createCase({
        name,
        target,
        target_type: targetType,
        objective,
        scope_acknowledged: ack
      });
      onCreated(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível criar o case.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <form className="modal case-modal" onSubmit={submit} onMouseDown={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <span className="eyebrow">new investigation</span>
            <h2>Defina o alvo e a pergunta</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose}><X size={18} /></button>
        </div>

        <label>
          Target
          <input
            autoFocus
            value={target}
            onChange={(e) => updateTarget(e.target.value)}
            placeholder="example.org, https://..., IP ou @conta-publica"
          />
        </label>

        <div className="two-col">
          <label>
            Tipo
            <select value={targetType} onChange={(e) => setTargetType(e.target.value as TargetType)}>
              <option value="domain">Domínio</option>
              <option value="organization">Organização / domínio</option>
              <option value="url">URL pública</option>
              <option value="ip">IP público</option>
              <option value="public_account">Conta pública</option>
            </select>
          </label>

          <label>
            Nome do case
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ex.: Brand impersonation Q3"
            />
          </label>
        </div>

        <label>
          Objective / intelligence question
          <textarea
            rows={3}
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            placeholder="Qual pergunta este case precisa responder?"
          />
        </label>

        {targetType === "public_account" && (
          <div className="scope-note">
            <ShieldCheck size={15} />
            Contas públicas usam observações/imports. O VIGIL não faz varredura automática de pessoas.
          </div>
        )}

        <label className="check">
          <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
          <span>Estou usando fontes públicas, finalidade legítima e escopo adequado.</span>
        </label>

        {error && <div className="form-error"><AlertTriangle size={15} />{error}</div>}

        <button className="primary wide" disabled={!name || !target || !ack || saving}>
          {saving ? "criando…" : "criar investigation"} <ChevronRight size={17} />
        </button>
      </form>
    </div>
  );
}

function FindingsPanel({
  workspace,
  caseId,
  onRefresh
}: {
  workspace: Workspace;
  caseId: string;
  onRefresh: () => void;
}) {
  async function pinFinding(id: string, label: string) {
    await api.addPin(caseId, { object_type: "finding", object_id: id, label });
    onRefresh();
  }

  return (
    <div className="panel-stack">
      <div className="section-toolbar">
        <div>
          <span className="eyebrow">assessments</span>
          <h2>Findings</h2>
          <p>Resultados analíticos, sempre separados das observações brutas.</p>
        </div>
        <span className="count-pill">{workspace.graph.findings.length}</span>
      </div>

      <div className="finding-grid">
        {workspace.graph.findings.map((finding) => (
          <article className="finding" key={finding.id}>
            <div className="finding-top">
              <span className={"severity " + finding.severity}>{finding.severity}</span>
              <b>{Math.round(finding.confidence * 100)}%</b>
            </div>
            <h3>{finding.title}</h3>
            <p>{finding.summary}</p>
            <div className="finding-foot">
              <small>{finding.category}</small>
              <button onClick={() => pinFinding(finding.id, finding.title)}>pin</button>
            </div>
          </article>
        ))}
        {!workspace.graph.findings.length && (
          <div className="empty-list"><FileSearch size={22} /><p>Nenhum finding produzido.</p></div>
        )}
      </div>
    </div>
  );
}

function AuditPanel({ workspace }: { workspace: Workspace }) {
  return (
    <div className="panel-stack">
      <div className="section-toolbar">
        <div>
          <span className="eyebrow">chain of analysis</span>
          <h2>Audit trail</h2>
          <p>Registro das principais mutações analíticas do case.</p>
        </div>
        <span className="count-pill">{workspace.audit.length}</span>
      </div>

      <div className="audit-list">
        {workspace.audit.map((item) => (
          <article key={item.id}>
            <span className="audit-icon"><ListChecks size={14} /></span>
            <div>
              <b>{item.action}</b>
              <small>{item.object_type}{item.object_id ? " · " + item.object_id.slice(0, 16) : ""}</small>
            </div>
            <code>{JSON.stringify(item.details)}</code>
            <time>{new Date(item.created_at).toLocaleString()}</time>
          </article>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [cases, setCases] = useState<Case[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [tab, setTab] = useState<Tab>("graph");
  const [newCase, setNewCase] = useState(false);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState("");

  async function refreshCases(preferred?: string) {
    const items = await api.cases();
    setCases(items);
    const id = preferred || selectedId || items[0]?.id || "";
    if (id) setSelectedId(id);
    return id;
  }

  async function refreshWorkspace(id = selectedId) {
    if (!id) {
      setWorkspace(null);
      return;
    }
    setWorkspace(await api.workspace(id));
  }

  useEffect(() => {
    Promise.all([api.cases(), api.modules()])
      .then(([items, moduleItems]) => {
        setCases(items);
        setModules(moduleItems);
        if (items[0]) setSelectedId(items[0].id);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (selectedId) {
      setWorkspace(null);
      api.workspace(selectedId)
        .then(setWorkspace)
        .catch(() => setWorkspace(null));
    }
  }, [selectedId]);

  const stats = useMemo(() => ({
    entities: workspace?.graph.entities.length || 0,
    edges: workspace?.graph.edges.length || 0,
    evidence: workspace?.graph.evidence.length || 0,
    findings: workspace?.graph.findings.length || 0,
    hypotheses: workspace?.hypotheses.length || 0,
    pins: workspace?.pins.length || 0
  }), [workspace]);

  async function run() {
    if (!workspace) return;
    setRunning(true);
    setNotice("");
    try {
      const result = await api.runCase(workspace.graph.case.id) as {
        warnings?: string[];
        entities_added?: number;
        evidence_added?: number;
      };
      await refreshWorkspace(workspace.graph.case.id);
      setNotice(
        result.warnings?.[0] ||
        `Coleta concluída · +${result.entities_added || 0} entities · +${result.evidence_added || 0} evidence`
      );
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Falha na coleta.");
    } finally {
      setRunning(false);
    }
  }

  const tabs: Array<[Tab, string, React.ComponentType<{ size?: number }>]> = [
    ["graph", "Graph", Network],
    ["evidence", "Evidence", Database],
    ["findings", "Findings", FileSearch],
    ["timeline", "Timeline", CalendarClock],
    ["map", "Map", Map],
    ["analysis", "Analysis", Lightbulb],
    ["report", "Report", FileText],
    ["modules", "Modules", Boxes],
    ["audit", "Audit", ListChecks]
  ];

  const currentCase = workspace?.graph.case;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><CircleDot size={20} /></div>
          <div><strong>VIGIL</strong><span>OSINT workbench</span></div>
        </div>

        <button className="primary new-button" onClick={() => setNewCase(true)}>
          <Plus size={16} /> new investigation
        </button>

        <div className="sidebar-label">cases</div>
        <div className="case-list">
          {cases.map((item) => (
            <button
              key={item.id}
              className={selectedId === item.id ? "case active" : "case"}
              onClick={() => setSelectedId(item.id)}
            >
              <span className="case-icon">
                {item.target_type === "public_account" ? <Search size={15} /> :
                 item.target_type === "url" ? <Globe2 size={15} /> :
                 <Network size={15} />}
              </span>
              <span>
                <b>{item.name}</b>
                <small>{item.target}</small>
              </span>
            </button>
          ))}
          {!cases.length && !loading && <p className="empty-sidebar">Nenhum case ainda.</p>}
        </div>

        <div className="sidebar-foot">
          <ShieldCheck size={15} />
          <span>public-source · provenance-first</span>
        </div>
      </aside>

      <main className="workspace">
        {!workspace ? (
          <div className="empty-state">
            <div className="radar"><span /><span /><span /><i /></div>
            <span className="eyebrow">investigation workspace</span>
            <h1>Do selector ao relatório.<br />Tudo no mesmo case.</h1>
            <p>
              Colete fontes públicas, correlacione entidades, revise relações, monte hipóteses,
              acompanhe a timeline e exporte um relatório rastreável.
            </p>
            <button className="primary" onClick={() => setNewCase(true)}>
              <Plus size={16} /> criar investigation
            </button>
          </div>
        ) : (
          <>
            <header className="topbar">
              <div className="title-block">
                <div className="breadcrumbs">
                  <span>cases</span><ChevronRight size={13} /><span>{currentCase?.target_type}</span>
                </div>
                <h1>{currentCase?.name}</h1>
                <div className="target-line">
                  <span className="status-dot" />
                  {currentCase?.target}
                  <span className="status-pill">{currentCase?.status}</span>
                </div>
              </div>

              <div className="top-actions">
                <button className="ghost" onClick={() => refreshWorkspace()}>
                  <RefreshCw size={14} /> refresh
                </button>
                <button className="primary" onClick={run} disabled={running}>
                  {running ? <RefreshCw className="spin" size={15} /> : <Play size={15} />}
                  {running ? "collecting" : "run public sources"}
                </button>
              </div>
            </header>

            {notice && (
              <div className="notice">
                {notice}
                <button onClick={() => setNotice("")}><X size={14} /></button>
              </div>
            )}

            <section className="stat-grid six">
              <div className="stat"><Network /><span><b>{stats.entities}</b> entities</span></div>
              <div className="stat"><Activity /><span><b>{stats.edges}</b> relations</span></div>
              <div className="stat"><Database /><span><b>{stats.evidence}</b> evidence</span></div>
              <div className="stat"><FileSearch /><span><b>{stats.findings}</b> findings</span></div>
              <div className="stat"><Lightbulb /><span><b>{stats.hypotheses}</b> hypotheses</span></div>
              <div className="stat"><FileText /><span><b>{stats.pins}</b> pinned</span></div>
            </section>

            <nav className="tabs scrollable">
              {tabs.map(([id, label, Icon]) => (
                <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
                  <Icon size={15} />{label}
                </button>
              ))}
            </nav>

            <section className="content">
              {tab === "graph" && (
                <>
                  <GraphCanvas
                    caseId={workspace.graph.case.id}
                    workspace={workspace}
                    onRefresh={() => refreshWorkspace()}
                  />
                  <ImportPanel
                    caseId={workspace.graph.case.id}
                    onDone={() => refreshWorkspace()}
                  />
                </>
              )}

              {tab === "evidence" && (
                <EvidencePanel
                  caseId={workspace.graph.case.id}
                  evidence={workspace.graph.evidence}
                  pins={workspace.pins}
                  snapshots={workspace.snapshots}
                  onRefresh={() => refreshWorkspace()}
                />
              )}

              {tab === "findings" && (
                <FindingsPanel
                  workspace={workspace}
                  caseId={workspace.graph.case.id}
                  onRefresh={() => refreshWorkspace()}
                />
              )}

              {tab === "timeline" && (
                <TimelinePanel
                  caseId={workspace.graph.case.id}
                  events={workspace.timeline}
                  onRefresh={() => refreshWorkspace()}
                />
              )}

              {tab === "map" && (
                <MapPanel
                  caseId={workspace.graph.case.id}
                  points={workspace.geo}
                  onRefresh={() => refreshWorkspace()}
                />
              )}

              {tab === "analysis" && (
                <AnalysisPanel
                  caseId={workspace.graph.case.id}
                  hypotheses={workspace.hypotheses}
                  notes={workspace.notes}
                  onRefresh={() => refreshWorkspace()}
                />
              )}

              {tab === "report" && (
                <ReportPanel
                  caseId={workspace.graph.case.id}
                  workspace={workspace}
                  onRefresh={() => refreshWorkspace()}
                />
              )}

              {tab === "modules" && <ModulesPanel modules={modules} />}
              {tab === "audit" && <AuditPanel workspace={workspace} />}
            </section>
          </>
        )}
      </main>

      {newCase && (
        <NewCaseModal
          onClose={() => setNewCase(false)}
          onCreated={async (created) => {
            setNewCase(false);
            await refreshCases(created.id);
            await refreshWorkspace(created.id);
          }}
        />
      )}
    </div>
  );
}
