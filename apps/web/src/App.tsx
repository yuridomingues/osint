import { useEffect, useMemo, useRef, useState } from "react";
import cytoscape, { Core } from "cytoscape";
import {
  Activity, AlertTriangle, Boxes, ChevronRight, CircleDot, Database,
  Download, FileJson, FileSearch, GitBranch, Network, Play, Plus,
  RefreshCw, Search, ShieldCheck, Upload, X
} from "lucide-react";
import { api, Case, Entity, Graph, TargetType } from "./api";

type Tab = "graph" | "evidence" | "findings" | "modules";

function percent(value: number) {
  return Math.round(value * 100) + "%";
}

function GraphCanvas({ graph }: { graph: Graph }) {
  const host = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const [selected, setSelected] = useState<Entity | null>(null);

  useEffect(() => {
    if (!host.current) return;
    cy.current?.destroy();

    const elements = [
      ...graph.entities.map((e) => ({
        data: { id: e.id, label: e.label, kind: e.kind, confidence: e.confidence }
      })),
      ...graph.edges.map((e) => ({
        data: {
          id: e.id,
          source: e.source_id,
          target: e.target_id,
          label: e.relation.replaceAll("_", " "),
          confidence: e.confidence
        }
      }))
    ];

    cy.current = cytoscape({
      container: host.current,
      elements,
      wheelSensitivity: 0.18,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#b9f56a",
            "border-color": "#0a0d0c",
            "border-width": 3,
            color: "#eff7ed",
            label: "data(label)",
            "font-size": 10,
            "text-wrap": "wrap",
            "text-max-width": 110,
            "text-valign": "bottom",
            "text-margin-y": 9,
            width: 38,
            height: 38
          }
        },
        { selector: 'node[kind = "domain"]', style: { "background-color": "#8aa7ff", shape: "diamond" } },
        { selector: 'node[kind = "hostname"]', style: { "background-color": "#7ed7c4", shape: "round-rectangle" } },
        { selector: 'node[kind = "nameserver"]', style: { "background-color": "#d3a7ff", shape: "hexagon" } },
        { selector: 'node[kind = "account"]', style: { "background-color": "#f4c86d", shape: "ellipse" } },
        {
          selector: "edge",
          style: {
            width: "mapData(confidence, 0, 1, 1, 4)",
            "line-color": "#52605a",
            "target-arrow-color": "#52605a",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            color: "#8d9c95",
            "font-size": 8,
            "text-background-color": "#111713",
            "text-background-opacity": 0.85,
            "text-background-padding": 3
          }
        },
        {
          selector: ":selected",
          style: { "border-color": "#ffffff", "border-width": 4, "line-color": "#b9f56a" }
        }
      ],
      layout: {
        name: "cose",
        animate: false,
        fit: true,
        padding: 48,
        nodeRepulsion: () => 9500,
        idealEdgeLength: () => 120
      }
    });

    cy.current.on("tap", "node", (evt) => {
      const id = evt.target.id();
      setSelected(graph.entities.find((e) => e.id === id) || null);
    });

    return () => cy.current?.destroy();
  }, [graph]);

  return (
    <div className="graph-shell">
      <div className="graph-toolbar">
        <div className="legend">
          <span><i className="dot domain" /> domain</span>
          <span><i className="dot account" /> account</span>
          <span><i className="dot host" /> host</span>
          <span><i className="dot infra" /> infra</span>
        </div>
        <button className="ghost small" onClick={() => cy.current?.fit(undefined, 50)}>
          <RefreshCw size={14} /> enquadrar
        </button>
      </div>
      <div className="graph-stage" ref={host} />
      {selected && (
        <aside className="entity-inspector">
          <button className="icon-button close" onClick={() => setSelected(null)}><X size={16}/></button>
          <span className="eyebrow">{selected.kind}</span>
          <h3>{selected.label}</h3>
          <div className="confidence"><span>confiança</span><b>{percent(selected.confidence)}</b></div>
          <div className="meter"><span style={{ width: percent(selected.confidence) }} /></div>
          <pre>{JSON.stringify(selected.properties, null, 2)}</pre>
        </aside>
      )}
    </div>
  );
}

function NewCaseModal({ onClose, onCreated }: { onClose: () => void; onCreated: (c: Case) => void }) {
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [targetType, setTargetType] = useState<TargetType>("domain");
  const [objective, setObjective] = useState("");
  const [ack, setAck] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
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
      setError(err instanceof Error ? err.message : "Não foi possível criar o caso");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <form className="modal" onSubmit={submit} onMouseDown={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div><span className="eyebrow">novo case</span><h2>Defina o escopo</h2></div>
          <button type="button" className="icon-button" onClick={onClose}><X size={18}/></button>
        </div>
        <label>
          Nome do caso
          <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex.: Brand impersonation Q3" />
        </label>
        <div className="two-col">
          <label>
            Tipo
            <select value={targetType} onChange={(e) => setTargetType(e.target.value as TargetType)}>
              <option value="domain">Domínio</option>
              <option value="organization">Organização / domínio</option>
              <option value="public_account">Conta pública</option>
            </select>
          </label>
          <label>
            Alvo
            <input value={target} onChange={(e) => setTarget(e.target.value)} placeholder={targetType === "public_account" ? "@handle" : "example.org"} />
          </label>
        </div>
        <label>
          Objetivo
          <textarea rows={3} value={objective} onChange={(e) => setObjective(e.target.value)} placeholder="O que esta investigação precisa responder?" />
        </label>
        <label className="check">
          <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
          <span>Estou usando fontes públicas, com finalidade legítima e escopo adequado.</span>
        </label>
        {error && <div className="form-error"><AlertTriangle size={15}/>{error}</div>}
        <button className="primary wide" disabled={!name || !target || !ack || saving}>
          {saving ? "Criando…" : "Criar case"} <ChevronRight size={17}/>
        </button>
      </form>
    </div>
  );
}

type ImportMode = "normalized" | "sherlock_csv" | "maigret_json" | "posts";

const importSamples: Record<ImportMode, string> = {
  normalized: `[
  {
    "platform": "github",
    "handle": "example",
    "profile_url": "https://github.com/example",
    "display_name": "Example",
    "bio": "Public profile observation",
    "external_urls": ["https://example.org"],
    "media_hashes": []
  }
]`,
  sherlock_csv: `username,name,url_main,url_user,exists,http_status,response_time_s
example,GitHub,https://github.com,https://github.com/example,Claimed,200,0.31`,
  maigret_json: `{
  "GitHub": {
    "username": "example",
    "url_user": "https://github.com/example",
    "status": "Claimed"
  }
}`,
  posts: `[
  {
    "platform": "example-platform",
    "author_handle": "account_a",
    "url": "https://example.org/post/1",
    "text": "Public post content",
    "published_at": "2026-09-11T12:00:00Z"
  }
]`
};

function ImportPanel({ caseId, onDone }: { caseId: string; onDone: () => void }) {
  const [mode, setMode] = useState<ImportMode>("normalized");
  const [value, setValue] = useState(importSamples.normalized);
  const [message, setMessage] = useState("");
  const [working, setWorking] = useState(false);

  function changeMode(next: ImportMode) {
    setMode(next);
    setValue(importSamples[next]);
    setMessage("");
  }

  async function send() {
    setMessage("");
    setWorking(true);
    try {
      let result: Record<string, unknown>;

      if (mode === "sherlock_csv" || mode === "maigret_json") {
        result = await api.importTool(caseId, mode, value) as Record<string, unknown>;
      } else {
        const parsed = JSON.parse(value);
        if (!Array.isArray(parsed)) throw new Error("Use um array JSON");
        result = mode === "posts"
          ? await api.importPosts(caseId, parsed) as Record<string, unknown>
          : await api.importObservations(caseId, parsed) as Record<string, unknown>;
      }

      const parts = [
        result.records_parsed !== undefined ? String(result.records_parsed) + " registros" : null,
        result.entities_added !== undefined ? String(result.entities_added) + " entidades" : null,
        result.evidence_added !== undefined ? String(result.evidence_added) + " evidências" : null,
        result.findings_added !== undefined ? String(result.findings_added) + " findings" : null
      ].filter(Boolean);

      setMessage(parts.join(" · ") || "Importação concluída.");
      onDone();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Não foi possível importar");
    } finally {
      setWorking(false);
    }
  }

  const description = mode === "posts"
    ? "Analisa datasets de posts públicos para detectar clusters de conteúdo idêntico sincronizado. O resultado é um indicador de coordenação, não atribuição de autoria."
    : "Normaliza resultados públicos no mesmo modelo de evidência. Relações só são criadas quando existem sinais independentes além de semelhança de nome.";

  return (
    <section className="import-card">
      <div>
        <span className="eyebrow">ingestão & correlação</span>
        <h3>Adicionar evidências ao case</h3>
        <p>{description}</p>
        <label className="import-mode">
          <span>formato</span>
          <select value={mode} onChange={(e) => changeMode(e.target.value as ImportMode)}>
            <option value="normalized">VIGIL · observações normalizadas</option>
            <option value="sherlock_csv">Sherlock · CSV</option>
            <option value="maigret_json">Maigret · JSON / NDJSON</option>
            <option value="posts">Posts públicos · coordenação</option>
          </select>
        </label>
      </div>
      <textarea value={value} onChange={(e) => setValue(e.target.value)} spellCheck={false} />
      <div className="import-actions">
        <span>{message}</span>
        <button className="secondary" onClick={send} disabled={working}>
          {working ? <RefreshCw className="spin" size={15}/> : <Upload size={15}/>}
          {working ? "importando" : "importar"}
        </button>
      </div>
    </section>
  );
}

export default function App() {
  const [cases, setCases] = useState<Case[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [graph, setGraph] = useState<Graph | null>(null);
  const [modules, setModules] = useState<Array<{id:string;name:string;mode:string;available:boolean}>>([]);
  const [tab, setTab] = useState<Tab>("graph");
  const [newCase, setNewCase] = useState(false);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState("");

  async function loadCases(preferred?: string) {
    const items = await api.cases();
    setCases(items);
    const id = preferred || selectedId || items[0]?.id || "";
    if (id) setSelectedId(id);
    return id;
  }

  async function loadGraph(id: string) {
    if (!id) {
      setGraph(null);
      return;
    }
    setGraph(await api.graph(id));
  }

  useEffect(() => {
    Promise.all([api.cases(), api.modules()])
      .then(([c, m]) => {
        setCases(c);
        setModules(m);
        if (c[0]) setSelectedId(c[0].id);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (selectedId) loadGraph(selectedId).catch(() => setGraph(null));
  }, [selectedId]);

  const stats = useMemo(() => ({
    entities: graph?.entities.length || 0,
    edges: graph?.edges.length || 0,
    evidence: graph?.evidence.length || 0,
    findings: graph?.findings.length || 0
  }), [graph]);

  async function run() {
    if (!graph) return;
    setRunning(true);
    setNotice("");
    try {
      const result = await api.runCase(graph.case.id) as {warnings?:string[]};
      await loadGraph(graph.case.id);
      setNotice(result.warnings?.[0] || "Coleta concluída e grafo atualizado.");
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "Falha na coleta");
    } finally {
      setRunning(false);
    }
  }

  const tabs: Array<[Tab, string, typeof Network]> = [
    ["graph", "Grafo", Network],
    ["evidence", "Evidências", Database],
    ["findings", "Findings", FileSearch],
    ["modules", "Módulos", Boxes]
  ];

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><CircleDot size={20}/></div>
          <div><strong>VIGIL</strong><span>OSINT workbench</span></div>
        </div>
        <button className="primary new-button" onClick={() => setNewCase(true)}><Plus size={16}/> novo case</button>
        <div className="sidebar-label">investigações</div>
        <div className="case-list">
          {cases.map((item) => (
            <button key={item.id} className={selectedId === item.id ? "case active" : "case"} onClick={() => setSelectedId(item.id)}>
              <span className="case-icon">{item.target_type === "public_account" ? <Search size={15}/> : <Network size={15}/>}</span>
              <span><b>{item.name}</b><small>{item.target}</small></span>
            </button>
          ))}
          {!cases.length && !loading && <p className="empty-sidebar">Nenhum case ainda.</p>}
        </div>
        <div className="sidebar-foot">
          <ShieldCheck size={15}/><span>public-source · provenance-first</span>
        </div>
      </aside>

      <main className="workspace">
        {!graph ? (
          <div className="empty-state">
            <div className="radar"><span/><span/><span/><i/></div>
            <span className="eyebrow">investigation workspace</span>
            <h1>Conecte evidências.<br/>Não confunda coincidência com prova.</h1>
            <p>Crie um case para montar um grafo rastreável de entidades, relações, fontes e confiança.</p>
            <button className="primary" onClick={() => setNewCase(true)}><Plus size={16}/> criar primeiro case</button>
          </div>
        ) : (
          <>
            <header className="topbar">
              <div className="title-block">
                <div className="breadcrumbs"><span>cases</span><ChevronRight size={13}/><span>{graph.case.target_type}</span></div>
                <h1>{graph.case.name}</h1>
                <div className="target-line"><span className="status-dot"/>{graph.case.target}<span className="status-pill">{graph.case.status}</span></div>
              </div>
              <div className="top-actions">
                <a className="ghost" href={api.exportUrl(graph.case.id, "graphml")}><Download size={15}/> GraphML</a>
                <a className="ghost" href={api.exportUrl(graph.case.id, "json")}><FileJson size={15}/> JSON</a>
                <button className="primary" onClick={run} disabled={running}>
                  {running ? <RefreshCw className="spin" size={15}/> : <Play size={15}/>}
                  {running ? "coletando" : "executar"}
                </button>
              </div>
            </header>

            {notice && <div className="notice">{notice}<button onClick={() => setNotice("")}><X size={14}/></button></div>}

            <section className="stat-grid">
              <div className="stat"><Network/><span><b>{stats.entities}</b> entidades</span></div>
              <div className="stat"><GitBranch/><span><b>{stats.edges}</b> relações</span></div>
              <div className="stat"><Database/><span><b>{stats.evidence}</b> evidências</span></div>
              <div className="stat"><Activity/><span><b>{stats.findings}</b> findings</span></div>
            </section>

            <nav className="tabs">
              {tabs.map(([id, label, Icon]) => (
                <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
                  <Icon size={15}/>{label}
                </button>
              ))}
            </nav>

            <section className="content">
              {tab === "graph" && (
                <>
                  <GraphCanvas graph={graph}/>
                  <ImportPanel caseId={graph.case.id} onDone={() => loadGraph(graph.case.id)}/>
                </>
              )}

              {tab === "evidence" && (
                <div className="table-card">
                  <div className="section-head"><div><span className="eyebrow">ledger</span><h2>Evidence ledger</h2></div><b>{graph.evidence.length}</b></div>
                  <div className="rows">
                    {graph.evidence.map((e) => (
                      <article className="evidence-row" key={e.id}>
                        <div className="source-icon"><Database size={16}/></div>
                        <div className="row-main"><b>{e.source}</b><span>{e.excerpt || e.collector}</span><small>{new Date(e.observed_at).toLocaleString()}</small></div>
                        <div className="reliability"><span>reliability</span><b>{percent(e.reliability)}</b></div>
                        {e.source_url && <a href={e.source_url} target="_blank" rel="noreferrer">fonte ↗</a>}
                      </article>
                    ))}
                    {!graph.evidence.length && <div className="empty-list">Ainda não há evidências neste case.</div>}
                  </div>
                </div>
              )}

              {tab === "findings" && (
                <div className="finding-grid">
                  {graph.findings.map((f) => (
                    <article className="finding" key={f.id}>
                      <div className="finding-top"><span className={"severity " + f.severity}>{f.severity}</span><b>{percent(f.confidence)}</b></div>
                      <h3>{f.title}</h3><p>{f.summary}</p><small>{f.category}</small>
                    </article>
                  ))}
                  {!graph.findings.length && <div className="empty-list">Nenhum finding produzido ainda.</div>}
                </div>
              )}

              {tab === "modules" && (
                <div className="module-grid">
                  {modules.map((m) => (
                    <article className="module" key={m.id}>
                      <div className="module-icon"><Boxes size={18}/></div>
                      <div><h3>{m.name}</h3><p>{m.id}</p></div>
                      <span className="mode">{m.mode}</span>
                      <span className={m.available ? "available" : "offline"}>{m.available ? "ready" : "offline"}</span>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </main>

      {newCase && <NewCaseModal onClose={() => setNewCase(false)} onCreated={async (c) => {
        setNewCase(false);
        await loadCases(c.id);
        await loadGraph(c.id);
      }}/>}
    </div>
  );
}
