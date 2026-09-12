import { useEffect, useMemo, useRef, useState } from "react";
import cytoscape, { Core, ElementDefinition } from "cytoscape";
import {
  BookmarkPlus, CheckCircle2, Filter, GitMerge, Pin as PinIcon, RefreshCw,
  Search, ShieldAlert, Split, X, XCircle
} from "lucide-react";
import { api, Edge, Entity, RelationReview, Workspace } from "../api";

type Selected =
  | { type: "entity"; item: Entity }
  | { type: "edge"; item: Edge }
  | null;

function percent(value: number) {
  return Math.round(value * 100) + "%";
}

function reviewFor(reviews: RelationReview[], edgeId: string) {
  return reviews.find((item) => item.edge_id === edgeId);
}

export default function GraphCanvas({
  caseId,
  workspace,
  onRefresh
}: {
  caseId: string;
  workspace: Workspace;
  onRefresh: () => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);

  const [selected, setSelected] = useState<Selected>(null);
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [minConfidence, setMinConfidence] = useState(0);
  const [layout, setLayout] = useState("cose");
  const [hideRejected, setHideRejected] = useState(true);
  const [clusterName, setClusterName] = useState("");
  const [clusterRationale, setClusterRationale] = useState("");
  const [reviewComment, setReviewComment] = useState("");
  const [viewName, setViewName] = useState("");
  const [selectedViewId, setSelectedViewId] = useState("");

  const kinds = useMemo(
    () => Array.from(new Set(workspace.graph.entities.map((e) => e.kind))).sort(),
    [workspace.graph.entities]
  );

  const filteredEntities = useMemo(() => {
    const q = query.trim().toLowerCase();
    return workspace.graph.entities.filter((entity) => {
      if (entity.confidence < minConfidence) return false;
      if (kind !== "all" && entity.kind !== kind) return false;
      if (!q) return true;
      return (
        entity.label.toLowerCase().includes(q) ||
        entity.kind.toLowerCase().includes(q) ||
        JSON.stringify(entity.properties).toLowerCase().includes(q)
      );
    });
  }, [workspace.graph.entities, query, kind, minConfidence]);

  const filteredIds = useMemo(
    () => new Set(filteredEntities.map((entity) => entity.id)),
    [filteredEntities]
  );

  const filteredEdges = useMemo(
    () => workspace.graph.edges.filter((edge) => {
      if (!filteredIds.has(edge.source_id) || !filteredIds.has(edge.target_id)) return false;
      const review = reviewFor(workspace.relation_reviews, edge.id);
      if (hideRejected && review?.state === "rejected") return false;
      return true;
    }),
    [workspace.graph.edges, workspace.relation_reviews, filteredIds, hideRejected]
  );

  useEffect(() => {
    if (!host.current) return;
    cy.current?.destroy();

    const elements: ElementDefinition[] = [
      ...filteredEntities.map((entity) => ({
        data: {
          id: entity.id,
          label: entity.label,
          kind: entity.kind,
          confidence: entity.confidence
        }
      })),
      ...filteredEdges.map((edge) => ({
        data: {
          id: edge.id,
          source: edge.source_id,
          target: edge.target_id,
          label: edge.relation.replaceAll("_", " "),
          confidence: edge.confidence,
          review: reviewFor(workspace.relation_reviews, edge.id)?.state || "unreviewed"
        }
      }))
    ];

    cy.current = cytoscape({
      container: host.current,
      elements,
      wheelSensitivity: 0.16,
      selectionType: "additive",
      boxSelectionEnabled: true,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#b9f56a",
            "border-color": "#090c0a",
            "border-width": 3,
            color: "#eff7ed",
            label: "data(label)",
            "font-size": 10,
            "text-wrap": "wrap",
            "text-max-width": 120,
            "text-valign": "bottom",
            "text-margin-y": 10,
            width: 40,
            height: 40
          }
        },
        { selector: 'node[kind = "domain"]', style: { "background-color": "#8aa7ff", shape: "diamond" } },
        { selector: 'node[kind = "url"]', style: { "background-color": "#a6bbff", shape: "round-rectangle" } },
        { selector: 'node[kind = "ip"]', style: { "background-color": "#78d6dc", shape: "hexagon" } },
        { selector: 'node[kind = "hostname"]', style: { "background-color": "#7ed7c4", shape: "round-rectangle" } },
        { selector: 'node[kind = "nameserver"]', style: { "background-color": "#d3a7ff", shape: "hexagon" } },
        { selector: 'node[kind = "account"]', style: { "background-color": "#f4c86d", shape: "ellipse" } },
        { selector: 'node[kind = "public_account"]', style: { "background-color": "#f4c86d", shape: "ellipse" } },
        { selector: 'node[kind = "image"]', style: { "background-color": "#eaa7ff", shape: "round-rectangle", width: 48, height: 38 } },
        { selector: 'node[kind = "publication"]', style: { "background-color": "#d4b6ff", shape: "round-rectangle" } },
        { selector: 'node[kind = "content_cluster"]', style: { "background-color": "#f19ac1", shape: "round-diamond" } },
        { selector: 'node[kind = "entity_cluster"]', style: { "background-color": "#f19ac1", shape: "star", width: 48, height: 48 } },
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
            "text-background-opacity": 0.88,
            "text-background-padding": 3
          }
        },
        {
          selector: 'edge[review = "confirmed"]',
          style: { "line-color": "#97d965", "target-arrow-color": "#97d965" }
        },
        {
          selector: 'edge[review = "needs_review"]',
          style: { "line-color": "#e4c96f", "target-arrow-color": "#e4c96f", "line-style": "dashed" }
        },
        {
          selector: 'edge[review = "rejected"]',
          style: { "line-color": "#cc7769", "target-arrow-color": "#cc7769", "line-style": "dotted", opacity: 0.55 }
        },
        {
          selector: ":selected",
          style: {
            "border-color": "#ffffff",
            "border-width": 4,
            "overlay-color": "#b9f56a",
            "overlay-opacity": 0.08
          }
        }
      ],
      layout: {
        name: layout,
        animate: false,
        fit: true,
        padding: 55
      }
    });

    const current = cy.current;

    current.on("tap", "node", (event) => {
      const item = workspace.graph.entities.find((entity) => entity.id === event.target.id());
      if (item) setSelected({ type: "entity", item });
    });

    current.on("tap", "edge", (event) => {
      const item = workspace.graph.edges.find((edge) => edge.id === event.target.id());
      if (item) {
        setSelected({ type: "edge", item });
        setReviewComment(reviewFor(workspace.relation_reviews, item.id)?.comment || "");
      }
    });

    current.on("select unselect", "node", () => {
      setSelectedNodeIds(current.nodes(":selected").map((node) => node.id()));
    });

    current.on("tap", (event) => {
      if (event.target === current) setSelected(null);
    });

    return () => current.destroy();
  }, [filteredEntities, filteredEdges, layout, workspace.graph.entities, workspace.graph.edges, workspace.relation_reviews]);

  function rerunLayout() {
    cy.current?.layout({ name: layout, animate: true, fit: true, padding: 55 }).run();
  }

  async function pinEntity(entity: Entity) {
    await api.addPin(caseId, {
      object_type: "entity",
      object_id: entity.id,
      label: entity.label
    });
    onRefresh();
  }

  async function pinEdge(edge: Edge) {
    await api.addPin(caseId, {
      object_type: "edge",
      object_id: edge.id,
      label: edge.relation
    });
    onRefresh();
  }

  async function reviewEdge(edge: Edge, state: "confirmed" | "rejected" | "needs_review") {
    await api.reviewEdge(caseId, edge.id, { state, comment: reviewComment });
    onRefresh();
  }

  async function createCluster() {
    if (selectedNodeIds.length < 2 || !clusterName.trim()) return;
    await api.createCluster(caseId, {
      label: clusterName.trim(),
      entity_ids: selectedNodeIds,
      rationale: clusterRationale.trim()
    });
    setClusterName("");
    setClusterRationale("");
    setSelectedNodeIds([]);
    onRefresh();
  }

  async function detachMember(clusterId: string, entityId: string) {
    await api.detachClusterMember(caseId, clusterId, entityId);
    onRefresh();
  }

  async function saveCurrentView() {
    const name = viewName.trim();
    if (!name) return;
    await api.saveView(caseId, {
      name,
      filters: { query, kind, minConfidence, hideRejected },
      layout: { name: layout }
    });
    setViewName("");
    onRefresh();
  }

  function loadSavedView(viewId: string) {
    setSelectedViewId(viewId);
    const view = workspace.saved_views.find((item) => item.id === viewId);
    if (!view) return;
    const filters = view.filters as Record<string, unknown>;
    const savedLayout = view.layout as Record<string, unknown>;
    if (typeof filters.query === "string") setQuery(filters.query);
    if (typeof filters.kind === "string") setKind(filters.kind);
    if (typeof filters.minConfidence === "number") setMinConfidence(filters.minConfidence);
    if (typeof filters.hideRejected === "boolean") setHideRejected(filters.hideRejected);
    if (typeof savedLayout.name === "string") setLayout(savedLayout.name);
  }

  const selectedReview = selected?.type === "edge"
    ? reviewFor(workspace.relation_reviews, selected.item.id)
    : undefined;

  return (
    <div className="graph-workbench">
      <div className="graph-filterbar">
        <label className="graph-search">
          <Search size={14} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="buscar no grafo..." />
        </label>

        <label>
          <Filter size={13} />
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="all">todos os tipos</option>
            {kinds.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>

        <label className="confidence-filter">
          <span>confidence ≥ {Math.round(minConfidence * 100)}%</span>
          <input
            type="range"
            min="0"
            max="100"
            value={Math.round(minConfidence * 100)}
            onChange={(e) => setMinConfidence(Number(e.target.value) / 100)}
          />
        </label>

        <label>
          <select value={layout} onChange={(e) => setLayout(e.target.value)}>
            <option value="cose">force</option>
            <option value="circle">circle</option>
            <option value="grid">grid</option>
            <option value="concentric">concentric</option>
          </select>
        </label>

        <button className="ghost small" onClick={rerunLayout}>
          <RefreshCw size={13} /> layout
        </button>

        <label className="check-inline">
          <input type="checkbox" checked={hideRejected} onChange={(e) => setHideRejected(e.target.checked)} />
          hide rejected
        </label>

        <label className="saved-view-select">
          <select value={selectedViewId} onChange={(e) => loadSavedView(e.target.value)}>
            <option value="">saved views</option>
            {workspace.saved_views.map((view) => (
              <option value={view.id} key={view.id}>{view.name}</option>
            ))}
          </select>
        </label>

        <label className="save-view-control">
          <input
            value={viewName}
            onChange={(e) => setViewName(e.target.value)}
            placeholder="nome da view"
          />
          <button className="ghost small" onClick={saveCurrentView} disabled={!viewName.trim()}>
            <BookmarkPlus size={13} /> save
          </button>
        </label>
      </div>

      <div className="graph-shell large">
        <div className="graph-stage full" ref={host} />

        <div className="graph-counts">
          <span>{filteredEntities.length} nodes</span>
          <span>{filteredEdges.length} edges</span>
          <span>{selectedNodeIds.length} selected</span>
        </div>

        {selected && (
          <aside className="entity-inspector wide">
            <button className="icon-button close" onClick={() => setSelected(null)}>
              <X size={16} />
            </button>

            {selected.type === "entity" ? (
              <>
                <span className="eyebrow">{selected.item.kind}</span>
                <h3>{selected.item.label}</h3>
                <div className="confidence">
                  <span>confidence</span>
                  <b>{percent(selected.item.confidence)}</b>
                </div>
                <div className="meter"><span style={{ width: percent(selected.item.confidence) }} /></div>

                <button className="secondary inspector-action" onClick={() => pinEntity(selected.item)}>
                  <PinIcon size={14} /> pin for report
                </button>

                {selected.item.kind === "entity_cluster" && Array.isArray(selected.item.properties.member_ids) && (
                  <div className="cluster-members">
                    <span>members</span>
                    {(selected.item.properties.member_ids as string[]).map((id) => {
                      const entity = workspace.graph.entities.find((item) => item.id === id);
                      return (
                        <div key={id}>
                          <small>{entity?.label || id}</small>
                          <button onClick={() => detachMember(selected.item.id, id)} title="detach">
                            <Split size={12} />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}

                <pre>{JSON.stringify(selected.item.properties, null, 2)}</pre>
              </>
            ) : (
              <>
                <span className="eyebrow">relationship</span>
                <h3>{selected.item.relation.replaceAll("_", " ")}</h3>
                <div className="confidence">
                  <span>confidence</span>
                  <b>{percent(selected.item.confidence)}</b>
                </div>
                <div className="meter"><span style={{ width: percent(selected.item.confidence) }} /></div>

                <div className={"review-state " + (selectedReview?.state || "unreviewed")}>
                  {selectedReview?.state || "unreviewed"}
                </div>

                <ul className="rationale-list">
                  {selected.item.rationale.map((reason) => <li key={reason}>{reason}</li>)}
                </ul>

                <textarea
                  className="review-comment"
                  placeholder="comentário da revisão..."
                  value={reviewComment}
                  onChange={(e) => setReviewComment(e.target.value)}
                />

                <div className="review-actions">
                  <button onClick={() => reviewEdge(selected.item, "confirmed")}><CheckCircle2 size={13}/> confirm</button>
                  <button onClick={() => reviewEdge(selected.item, "needs_review")}><ShieldAlert size={13}/> review</button>
                  <button onClick={() => reviewEdge(selected.item, "rejected")}><XCircle size={13}/> reject</button>
                </div>

                <button className="secondary inspector-action" onClick={() => pinEdge(selected.item)}>
                  <PinIcon size={14} /> pin for report
                </button>
              </>
            )}
          </aside>
        )}
      </div>

      {selectedNodeIds.length >= 2 && (
        <div className="cluster-bar">
          <div>
            <GitMerge size={16} />
            <span><b>{selectedNodeIds.length}</b> entidades selecionadas</span>
          </div>
          <input
            placeholder="nome do cluster"
            value={clusterName}
            onChange={(e) => setClusterName(e.target.value)}
          />
          <input
            placeholder="rationale"
            value={clusterRationale}
            onChange={(e) => setClusterRationale(e.target.value)}
          />
          <button className="primary" onClick={createCluster} disabled={!clusterName.trim()}>
            agrupar
          </button>
        </div>
      )}
    </div>
  );
}
