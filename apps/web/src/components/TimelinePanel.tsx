import { useMemo, useState } from "react";
import { CalendarClock, ExternalLink, Plus, RefreshCw } from "lucide-react";
import { api, TimelineEvent } from "../api";

export default function TimelinePanel({
  caseId,
  events,
  onRefresh
}: {
  caseId: string;
  events: TimelineEvent[];
  onRefresh: () => void;
}) {
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [eventAt, setEventAt] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("analyst");
  const [busy, setBusy] = useState(false);

  const sorted = useMemo(
    () => [...events].sort((a, b) => a.event_at.localeCompare(b.event_at)),
    [events]
  );

  async function generate() {
    setBusy(true);
    try {
      await api.generateTimeline(caseId);
      onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function add() {
    if (!title || !eventAt) return;
    setBusy(true);
    try {
      await api.addTimelineEvent(caseId, {
        title,
        description,
        event_at: new Date(eventAt).toISOString(),
        category
      });
      setTitle("");
      setEventAt("");
      setDescription("");
      setShowForm(false);
      onRefresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel-stack">
      <div className="section-toolbar">
        <div>
          <span className="eyebrow">chronology</span>
          <h2>Timeline</h2>
          <p>Contexto temporal de evidências e eventos analíticos.</p>
        </div>
        <div className="toolbar-actions">
          <button className="ghost" onClick={generate} disabled={busy}>
            <RefreshCw size={14} /> gerar de evidências
          </button>
          <button className="secondary" onClick={() => setShowForm(!showForm)}>
            <Plus size={14} /> evento
          </button>
        </div>
      </div>

      {showForm && (
        <div className="inline-form timeline-form">
          <input placeholder="Título" value={title} onChange={(e) => setTitle(e.target.value)} />
          <input type="datetime-local" value={eventAt} onChange={(e) => setEventAt(e.target.value)} />
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="analyst">analyst</option>
            <option value="evidence">evidence</option>
            <option value="incident">incident</option>
            <option value="publication">publication</option>
          </select>
          <textarea placeholder="Descrição" value={description} onChange={(e) => setDescription(e.target.value)} />
          <button className="primary" onClick={add} disabled={!title || !eventAt || busy}>salvar</button>
        </div>
      )}

      <div className="timeline">
        {sorted.map((event) => (
          <article className="timeline-item" key={event.id}>
            <div className="timeline-rail">
              <span className="timeline-dot" />
              <i />
            </div>
            <div className="timeline-time">
              <b>{new Date(event.event_at).toLocaleDateString()}</b>
              <span>{new Date(event.event_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
            </div>
            <div className="timeline-card">
              <div className="timeline-card-top">
                <span className="mode">{event.category}</span>
                {event.source_url && (
                  <a href={event.source_url} target="_blank" rel="noreferrer">
                    fonte <ExternalLink size={12} />
                  </a>
                )}
              </div>
              <h3>{event.title}</h3>
              <p>{event.description || "Sem descrição adicional."}</p>
            </div>
          </article>
        ))}
        {!sorted.length && (
          <div className="empty-list">
            <CalendarClock size={22} />
            <p>A timeline ainda está vazia.</p>
          </div>
        )}
      </div>
    </div>
  );
}
