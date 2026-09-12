import { useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, Boxes, Building2, CalendarClock, ChevronRight, CircleDot,
  Database, FileSearch, FileText, Globe2, Image as ImageIcon, LayoutDashboard, Lightbulb, ListChecks, Map,
  Network, Play, Plus, RefreshCw, Search, ShieldCheck, UserRoundSearch, X
} from "lucide-react";
import { api, Case, ModuleInfo, TargetType, Workspace } from "./api";
import AnalysisPanel from "./components/AnalysisPanel";
import EvidencePanel from "./components/EvidencePanel";
import GraphCanvas from "./components/GraphCanvas";
import ImportPanel from "./components/ImportPanel";
import ImagePanel from "./components/ImagePanel";
import MapPanel from "./components/MapPanel";
import ModulesPanel from "./components/ModulesPanel";
import OverviewPanel from "./components/OverviewPanel";
import ReportPanel from "./components/ReportPanel";
import TimelinePanel from "./components/TimelinePanel";

type Tab =
  | "overview"
  | "graph"
  | "evidence"
  | "image"
  | "findings"
  | "timeline"
  | "map"
  | "analysis"
  | "report"
  | "modules"
  | "audit";

function guessTargetType(value: string): TargetType {
  const target = value.trim();
  if (/^https?:\/\//i.test(target)) {
    try {
      const host = new URL(target).hostname.toLowerCase().replace(/^www\./, "");
      if ([
        "instagram.com", "x.com", "twitter.com", "github.com", "linkedin.com",
        "substack.com", "medium.com", "tiktok.com", "youtube.com", "bsky.app"
      ].includes(host)) return "public_account";
    } catch {
      // keep URL fallback below
    }
    return "url";
  }
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
  const [targetType, setTargetType] = useState<TargetType>("public_account");
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

        <div className="case-type-block">
          <span className="field-label">O que você quer investigar?</span>
          <div className="case-type-grid">
            {[
              ["public_account", "Pessoa / perfil público", "Instagram, X, GitHub, Substack…", UserRoundSearch],
              ["domain", "Site / domínio", "Domínios, subdomínios e histórico", Globe2],
              ["organization", "Empresa / organização", "Infraestrutura pública relacionada", Building2],
              ["url", "Página específica", "Histórico e contexto de uma URL", FileSearch],
              ["ip", "IP público", "Dono da faixa e contexto técnico", Network]
            ].map(([value, label, help, Icon]) => (
              <button
                key={String(value)}
                type="button"
                className={targetType === value ? "case-type active" : "case-type"}
                onClick={() => setTargetType(value as TargetType)}
              >
                <Icon size={17} />
                <span><b>{String(label)}</b><small>{String(help)}</small></span>
              </button>
            ))}
          </div>
        </div>

        <label>
          Nome da investigação
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ex.: Minha presença pública"
          />
        </label>

        <label>
          Objective / intelligence question
          <textarea
            rows={3}
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            placeholder="Ex.: Quero descobrir onde esse perfil aparece publicamente e quais contas parecem relacionadas."
          />
        </label>

        {targetType === "public_account" && (
          <div className="scope-note">
            <ShieldCheck size={15} />
            O VIGIL consulta somente fontes públicas e mostra a evidência por trás de cada conexão. Não usa reconhecimento facial nem dados privados como atalho.
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
  const [tab, setTab] = useState<Tab>("overview");
  const [newCase, setNewCase] = useState(false);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

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

  const tabs: Array<[Tab, string, React.ComponentType<{ size?: number }>, boolean?]> = [
    ["overview", "Visão geral", LayoutDashboard],
    ["graph", "Conexões", Network],
    ["evidence", "Fontes", Database],
    ["image", "Imagens", ImageIcon],
    ["findings", "Achados", FileSearch],
    ["timeline", "Linha do tempo", CalendarClock],
    ["map", "Mapa", Map],
    ["analysis", "Análise", Lightbulb],
    ["report", "Relatório", FileText],
    ["modules", "Módulos", Boxes, true],
    ["audit", "Auditoria", ListChecks, true]
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
              Comece com um perfil, site, organização, URL ou IP. O VIGIL escolhe as fontes adequadas,
              explica o que encontrou e mantém cada conclusão ligada à evidência.
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

            {window.location.hostname.endsWith("vercel.app") && (
              <div className="cloud-test-banner">
                <AlertTriangle size={13} />
                <b>Ambiente de teste</b>
                <span>o app está online para testes; os cases podem resetar até conectarmos persistência cloud.</span>
              </div>
            )}

            <section className="stat-grid six">
              <div className="stat"><Network /><span><b>{stats.entities}</b> itens</span></div>
              <div className="stat"><Activity /><span><b>{stats.edges}</b> conexões</span></div>
              <div className="stat"><Database /><span><b>{stats.evidence}</b> fontes</span></div>
              <div className="stat"><FileSearch /><span><b>{stats.findings}</b> achados</span></div>
              <div className="stat"><Lightbulb /><span><b>{stats.hypotheses}</b> hipóteses</span></div>
              <div className="stat"><FileText /><span><b>{stats.pins}</b> selecionados</span></div>
            </section>

            <nav className="tabs scrollable">
              {tabs.filter(([, , , advanced]) => !advanced || showAdvanced).map(([id, label, Icon, advanced]) => (
                <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
                  <Icon size={15} />{label}{advanced ? <small>avançado</small> : null}
                </button>
              ))}
              <button className={showAdvanced ? "advanced-toggle active" : "advanced-toggle"} onClick={() => setShowAdvanced((value) => !value)}>
                <Boxes size={14} /> {showAdvanced ? "ocultar avançado" : "mostrar avançado"}
              </button>
            </nav>

            <section className="content">
              {tab === "overview" && (
                <OverviewPanel
                  workspace={workspace}
                  running={running}
                  onRun={run}
                  onOpenTab={(next) => setTab(next)}
                />
              )}

              {tab === "graph" && (
                <>
                  <GraphCanvas
                    caseId={workspace.graph.case.id}
                    workspace={workspace}
                    onRefresh={() => refreshWorkspace()}
                  />
                  <ImportPanel
                    caseId={workspace.graph.case.id}
                    targetType={workspace.graph.case.target_type}
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

              {tab === "image" && (
                <ImagePanel
                  caseId={workspace.graph.case.id}
                  workspace={workspace}
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
