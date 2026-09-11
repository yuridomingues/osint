import { useMemo, useState } from "react";
import { Camera, ExternalLink, Pin as PinIcon, Search } from "lucide-react";
import { api, Evidence, Pin, Snapshot } from "../api";

export default function EvidencePanel({
  caseId,
  evidence,
  pins,
  snapshots,
  onRefresh
}: {
  caseId: string;
  evidence: Evidence[];
  pins: Pin[];
  snapshots: Snapshot[];
  onRefresh: () => void;
}) {
  const [query, setQuery] = useState("");

  const pinnedIds = useMemo(
    () => new Set(pins.filter((p) => p.object_type === "evidence").map((p) => p.object_id)),
    [pins]
  );
  const snapIds = useMemo(
    () => new Set(snapshots.map((s) => s.evidence_id)),
    [snapshots]
  );

  const filtered = evidence.filter((item) => {
    const q = query.toLowerCase().trim();
    if (!q) return true;
    return (
      item.source.toLowerCase().includes(q) ||
      item.collector.toLowerCase().includes(q) ||
      item.excerpt.toLowerCase().includes(q) ||
      JSON.stringify(item.metadata).toLowerCase().includes(q)
    );
  });

  async function pin(item: Evidence) {
    await api.addPin(caseId, {
      object_type: "evidence",
      object_id: item.id,
      label: item.source
    });
    onRefresh();
  }

  async function snapshot(item: Evidence) {
    await api.snapshotEvidence(caseId, item.id);
    onRefresh();
  }

  return (
    <div className="panel-stack">
      <div className="section-toolbar">
        <div>
          <span className="eyebrow">provenance</span>
          <h2>Evidence ledger</h2>
          <p>Fonte, collector, reliability, timestamp e hash em um único ledger.</p>
        </div>
        <label className="panel-search">
          <Search size={14} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="filtrar evidências..." />
        </label>
      </div>

      <div className="evidence-grid">
        {filtered.map((item) => (
          <article className="evidence-card" key={item.id}>
            <div className="evidence-card-head">
              <div>
                <span className="eyebrow">{item.collector}</span>
                <h3>{item.source}</h3>
              </div>
              <div className="evidence-score">{Math.round(item.reliability * 100)}%</div>
            </div>

            <p>{item.excerpt || "Sem excerpt."}</p>

            <dl>
              <div><dt>observed</dt><dd>{new Date(item.observed_at).toLocaleString()}</dd></div>
              <div><dt>hash</dt><dd>{item.content_hash ? item.content_hash.slice(0, 18) + "…" : "n/a"}</dd></div>
            </dl>

            <div className="evidence-card-actions">
              <button className={pinnedIds.has(item.id) ? "chip active" : "chip"} onClick={() => pin(item)}>
                <PinIcon size={12} /> {pinnedIds.has(item.id) ? "pinned" : "pin"}
              </button>
              <button className={snapIds.has(item.id) ? "chip active" : "chip"} onClick={() => snapshot(item)}>
                <Camera size={12} /> {snapIds.has(item.id) ? "snapshotted" : "snapshot"}
              </button>
              {item.source_url && (
                <a className="chip" href={item.source_url} target="_blank" rel="noreferrer">
                  fonte <ExternalLink size={11} />
                </a>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
