import { useState } from "react";
import { CheckCircle2, CircleDashed, Lightbulb, Plus, Trash2, XCircle } from "lucide-react";
import { api, Hypothesis, HypothesisStatus, Note } from "../api";

function statusIcon(status: HypothesisStatus) {
  if (status === "supported") return <CheckCircle2 size={14} />;
  if (status === "rejected") return <XCircle size={14} />;
  return <CircleDashed size={14} />;
}

export default function AnalysisPanel({
  caseId,
  hypotheses,
  notes,
  onRefresh
}: {
  caseId: string;
  hypotheses: Hypothesis[];
  notes: Note[];
  onRefresh: () => void;
}) {
  const [hypTitle, setHypTitle] = useState("");
  const [hypStatement, setHypStatement] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [noteTags, setNoteTags] = useState("");
  const [busy, setBusy] = useState(false);

  async function addHypothesis() {
    if (!hypTitle || !hypStatement) return;
    setBusy(true);
    try {
      await api.addHypothesis(caseId, {
        title: hypTitle,
        statement: hypStatement,
        status: "open",
        confidence: 0.5
      });
      setHypTitle("");
      setHypStatement("");
      onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(item: Hypothesis, status: HypothesisStatus) {
    await api.updateHypothesis(caseId, item.id, { status });
    onRefresh();
  }

  async function setConfidence(item: Hypothesis, confidence: number) {
    await api.updateHypothesis(caseId, item.id, { confidence });
    onRefresh();
  }

  async function addNote() {
    if (!noteBody) return;
    setBusy(true);
    try {
      await api.addNote(caseId, {
        body: noteBody,
        tags: noteTags.split(",").map((x) => x.trim()).filter(Boolean)
      });
      setNoteBody("");
      setNoteTags("");
      onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function removeNote(noteId: string) {
    await api.deleteNote(caseId, noteId);
    onRefresh();
  }

  return (
    <div className="analysis-grid">
      <section className="analysis-column">
        <div className="section-toolbar compact">
          <div>
            <span className="eyebrow">analysis</span>
            <h2>Hypotheses</h2>
          </div>
          <span className="count-pill">{hypotheses.length}</span>
        </div>

        <div className="analysis-form">
          <input placeholder="Hipótese" value={hypTitle} onChange={(e) => setHypTitle(e.target.value)} />
          <textarea
            placeholder="O que precisa ser verdadeiro? Que evidência apoiaria ou derrubaria isso?"
            value={hypStatement}
            onChange={(e) => setHypStatement(e.target.value)}
          />
          <button className="secondary" onClick={addHypothesis} disabled={!hypTitle || !hypStatement || busy}>
            <Plus size={14} /> adicionar hipótese
          </button>
        </div>

        <div className="hypothesis-list">
          {hypotheses.map((item) => (
            <article className={"hypothesis-card " + item.status} key={item.id}>
              <div className="hypothesis-head">
                <span className={"hypothesis-status " + item.status}>
                  {statusIcon(item.status)} {item.status}
                </span>
                <b>{Math.round(item.confidence * 100)}%</b>
              </div>
              <h3>{item.title}</h3>
              <p>{item.statement}</p>

              {item.counterpoints.length > 0 && (
                <div className="counterpoints">
                  <span>counterpoints</span>
                  {item.counterpoints.map((point, index) => <small key={index}>{point}</small>)}
                </div>
              )}

              <label className="confidence-slider">
                <span>confidence</span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={Math.round(item.confidence * 100)}
                  onChange={(e) => setConfidence(item, Number(e.target.value) / 100)}
                />
              </label>

              <div className="hypothesis-actions">
                <button onClick={() => setStatus(item, "supported")}>supported</button>
                <button onClick={() => setStatus(item, "rejected")}>rejected</button>
                <button onClick={() => setStatus(item, "inconclusive")}>inconclusive</button>
              </div>
            </article>
          ))}
          {!hypotheses.length && (
            <div className="empty-list">
              <Lightbulb size={22} />
              <p>Nenhuma hipótese analítica ainda.</p>
            </div>
          )}
        </div>
      </section>

      <section className="analysis-column">
        <div className="section-toolbar compact">
          <div>
            <span className="eyebrow">working notes</span>
            <h2>Notes</h2>
          </div>
          <span className="count-pill">{notes.length}</span>
        </div>

        <div className="analysis-form">
          <textarea
            placeholder="Anotação investigativa, dúvida, próximos passos..."
            value={noteBody}
            onChange={(e) => setNoteBody(e.target.value)}
          />
          <input
            placeholder="tags, separadas, por vírgula"
            value={noteTags}
            onChange={(e) => setNoteTags(e.target.value)}
          />
          <button className="secondary" onClick={addNote} disabled={!noteBody || busy}>
            <Plus size={14} /> adicionar nota
          </button>
        </div>

        <div className="note-list">
          {notes.map((note) => (
            <article className="note-card" key={note.id}>
              <button className="note-delete" onClick={() => removeNote(note.id)}>
                <Trash2 size={13} />
              </button>
              <p>{note.body}</p>
              <div className="tag-row">
                {note.tags.map((tag) => <span key={tag}>{tag}</span>)}
              </div>
              <small>{new Date(note.updated_at).toLocaleString()}</small>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
