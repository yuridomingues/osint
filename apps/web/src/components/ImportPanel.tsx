import { useState } from "react";
import { RefreshCw, Upload } from "lucide-react";
import { api } from "../api";

type ImportMode = "normalized" | "sherlock_csv" | "maigret_json" | "posts";

const samples: Record<ImportMode, string> = {
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

export default function ImportPanel({
  caseId,
  onDone
}: {
  caseId: string;
  onDone: () => void;
}) {
  const [mode, setMode] = useState<ImportMode>("normalized");
  const [value, setValue] = useState(samples.normalized);
  const [message, setMessage] = useState("");
  const [working, setWorking] = useState(false);

  function changeMode(next: ImportMode) {
    setMode(next);
    setValue(samples[next]);
    setMessage("");
  }

  async function send() {
    setWorking(true);
    setMessage("");
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
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Falha na importação");
    } finally {
      setWorking(false);
    }
  }

  return (
    <section className="import-card">
      <div>
        <span className="eyebrow">ingestão</span>
        <h3>Adicionar evidências</h3>
        <p>
          Normalize resultados públicos no mesmo evidence ledger. Relações de identidade
          exigem sinais independentes além de nomes parecidos.
        </p>
        <label className="import-mode">
          <span>formato</span>
          <select value={mode} onChange={(e) => changeMode(e.target.value as ImportMode)}>
            <option value="normalized">VIGIL · observações</option>
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
          {working ? <RefreshCw className="spin" size={15} /> : <Upload size={15} />}
          {working ? "importando" : "importar"}
        </button>
      </div>
    </section>
  );
}
