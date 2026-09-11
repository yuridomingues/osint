import { useMemo } from "react";
import {
  Download, FileCode2, FileJson, FileSpreadsheet, Network, Pin as PinIcon, Printer
} from "lucide-react";
import { api, Workspace } from "../api";

function resolvePin(workspace: Workspace, objectType: string, objectId: string) {
  if (objectType === "entity") return workspace.graph.entities.find((x) => x.id === objectId)?.label;
  if (objectType === "edge") return workspace.graph.edges.find((x) => x.id === objectId)?.relation;
  if (objectType === "evidence") return workspace.graph.evidence.find((x) => x.id === objectId)?.source;
  if (objectType === "finding") return workspace.graph.findings.find((x) => x.id === objectId)?.title;
  if (objectType === "note") return workspace.notes.find((x) => x.id === objectId)?.body.slice(0, 60);
  if (objectType === "hypothesis") return workspace.hypotheses.find((x) => x.id === objectId)?.title;
  return objectId;
}

export default function ReportPanel({
  caseId,
  workspace,
  onRefresh
}: {
  caseId: string;
  workspace: Workspace;
  onRefresh: () => void;
}) {
  const pinned = useMemo(
    () => workspace.pins.map((pin) => ({
      ...pin,
      resolved: pin.label || resolvePin(workspace, pin.object_type, pin.object_id) || pin.object_id
    })),
    [workspace]
  );

  async function remove(pinId: string) {
    await api.deletePin(caseId, pinId);
    onRefresh();
  }

  return (
    <div className="report-layout">
      <section className="report-builder">
        <div className="section-toolbar">
          <div>
            <span className="eyebrow">curation</span>
            <h2>Report builder</h2>
            <p>O relatório curado usa somente os objetos pinned; o full report inclui o case inteiro.</p>
          </div>
          <div className="report-counter"><PinIcon size={15} /><b>{pinned.length}</b> pinned</div>
        </div>

        <div className="pin-board">
          {pinned.map((pin) => (
            <article key={pin.id}>
              <div>
                <span className="mode">{pin.object_type}</span>
                <b>{pin.resolved}</b>
              </div>
              <button onClick={() => remove(pin.id)}>remove</button>
            </article>
          ))}
          {!pinned.length && (
            <div className="empty-list">
              <PinIcon size={21} />
              <p>Pin entities, edges, evidence ou hypotheses para montar um relatório curado.</p>
            </div>
          )}
        </div>
      </section>

      <aside className="export-panel">
        <span className="eyebrow">exports</span>
        <h3>Full report</h3>
        <a className="export-button primary-export" href={api.reportUrl(caseId, "html", false)} target="_blank" rel="noreferrer">
          <Printer size={16} /><span><b>Print-ready HTML / PDF</b><small>abre e dispara o print dialog</small></span>
        </a>
        <a className="export-button" href={api.reportUrl(caseId, "md", false)}>
          <FileCode2 size={16} /><span><b>Markdown</b><small>narrativa completa</small></span>
        </a>
        <a className="export-button" href={api.reportUrl(caseId, "csv", false)}>
          <FileSpreadsheet size={16} /><span><b>Evidence CSV</b><small>ledger tabular</small></span>
        </a>

        <h3>Curated report</h3>
        <a className="export-button" href={api.reportUrl(caseId, "html", true)} target="_blank" rel="noreferrer">
          <Printer size={16} /><span><b>Pinned-only HTML / PDF</b><small>somente itens selecionados</small></span>
        </a>
        <a className="export-button" href={api.reportUrl(caseId, "md", true)}>
          <Download size={16} /><span><b>Pinned-only Markdown</b><small>handoff leve</small></span>
        </a>

        <h3>Raw data</h3>
        <a className="export-button" href={api.exportUrl(caseId, "json")}>
          <FileJson size={16} /><span><b>JSON</b><small>case graph completo</small></span>
        </a>
        <a className="export-button" href={api.exportUrl(caseId, "graphml")}>
          <Network size={16} /><span><b>GraphML</b><small>link-analysis tools</small></span>
        </a>
      </aside>
    </div>
  );
}
