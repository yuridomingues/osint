import { useMemo, useState } from "react";
import { Image as ImageIcon, Search, ShieldCheck, Upload } from "lucide-react";
import { api, Workspace } from "../api";

type ImageResult = {
  entity_id: string;
  evidence_id: string;
  analysis: {
    sha256: string;
    byte_size: number;
    format: string;
    width: number;
    height: number;
    ahash: string;
    dhash: string;
    exif: Record<string, unknown>;
    c2pa: Record<string, unknown>;
  };
  local_matches: Array<{
    entity_id: string;
    label: string;
    confidence: number;
    reasons: string[];
  }>;
  reverse_image_matches: Array<{
    score?: number | null;
    domain?: string | null;
    image_url?: string | null;
    backlinks: string[];
  }>;
  warning?: string | null;
};

function bytesLabel(value: number) {
  if (value < 1024) return value + " B";
  if (value < 1024 * 1024) return (value / 1024).toFixed(1) + " KB";
  return (value / (1024 * 1024)).toFixed(2) + " MB";
}

export default function ImagePanel({
  caseId,
  workspace,
  onRefresh
}: {
  caseId: string;
  workspace: Workspace;
  onRefresh: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [searchWeb, setSearchWeb] = useState(true);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ImageResult | null>(null);
  const [error, setError] = useState("");

  const preview = useMemo(() => file ? URL.createObjectURL(file) : "", [file]);

  async function analyze() {
    if (!file) return;
    if (file.size > 12 * 1024 * 1024) {
      setError("A imagem excede o limite de 12 MB.");
      return;
    }
    setRunning(true);
    setError("");
    try {
      const dataBase64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          const value = String(reader.result || "");
          resolve(value.includes(",") ? value.split(",", 2)[1] : value);
        };
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
      });
      const response = await api.addImageEvidence(caseId, {
        filename: file.name,
        content_type: file.type || "application/octet-stream",
        data_base64: dataBase64,
        search_web: searchWeb
      }) as ImageResult;
      setResult(response);
      onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao analisar a imagem.");
    } finally {
      setRunning(false);
    }
  }

  const imageEntities = workspace.graph.entities.filter((item) => item.kind === "image");

  return (
    <div className="panel-stack">
      <div className="section-toolbar">
        <div>
          <span className="eyebrow">visual evidence</span>
          <h2>Image evidence</h2>
          <p>Hashes, EXIF, C2PA e busca por cópias/derivações da imagem. Sem reconhecimento facial.</p>
        </div>
        <span className="count-pill">{imageEntities.length} images</span>
      </div>

      <div className="image-evidence-layout">
        <section className="image-upload-card">
          <label className="image-drop">
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif,image/bmp,image/tiff"
              onChange={(e) => {
                setFile(e.target.files?.[0] || null);
                setResult(null);
                setError("");
              }}
            />
            {preview ? (
              <img src={preview} alt="preview" />
            ) : (
              <div>
                <Upload size={24} />
                <b>Escolha uma imagem</b>
                <small>JPEG, PNG, WebP, GIF, BMP ou TIFF · até 12 MB</small>
              </div>
            )}
          </label>

          <label className="check image-search-toggle">
            <input type="checkbox" checked={searchWeb} onChange={(e) => setSearchWeb(e.target.checked)} />
            <span>
              <b>Reverse-image web search</b>
              <small>Procura a mesma imagem ou versões modificadas quando um provider estiver configurado.</small>
            </span>
          </label>

          <div className="scope-note">
            <ShieldCheck size={15} />
            O VIGIL não identifica quem aparece na foto. A correlação visual é baseada no arquivo/imagem reutilizada.
          </div>

          {error && <div className="form-error">{error}</div>}
          <button className="primary wide" disabled={!file || running} onClick={analyze}>
            {running ? "analisando…" : <><Search size={15} /> analisar imagem</>}
          </button>
        </section>

        <section className="image-result-card">
          {!result ? (
            <div className="empty-list">
              <ImageIcon size={24} />
              <p>Adicione uma imagem para gerar fingerprints e procurar reutilizações.</p>
            </div>
          ) : (
            <>
              <div className="image-result-head">
                <div>
                  <span className="eyebrow">fingerprint</span>
                  <h3>{result.analysis.format} · {result.analysis.width}×{result.analysis.height}</h3>
                </div>
                <b>{bytesLabel(result.analysis.byte_size)}</b>
              </div>

              <dl className="image-meta">
                <div><dt>SHA-256</dt><dd>{result.analysis.sha256}</dd></div>
                <div><dt>aHash</dt><dd>{result.analysis.ahash}</dd></div>
                <div><dt>dHash</dt><dd>{result.analysis.dhash}</dd></div>
                <div><dt>EXIF</dt><dd>{Object.keys(result.analysis.exif || {}).length} campos seguros</dd></div>
                <div><dt>C2PA</dt><dd>{String(result.analysis.c2pa?.validation || "not_checked")}</dd></div>
              </dl>

              <div className="image-match-summary">
                <article>
                  <b>{result.local_matches.length}</b>
                  <span>matches no case</span>
                </article>
                <article>
                  <b>{result.reverse_image_matches.length}</b>
                  <span>reverse-image matches</span>
                </article>
              </div>

              {result.warning && <div className="image-warning">{result.warning}</div>}

              {!!result.local_matches.length && (
                <div className="image-match-list">
                  <h4>Media reuse</h4>
                  {result.local_matches.map((match) => (
                    <article key={match.entity_id}>
                      <div><b>{match.label}</b><small>{match.reasons.join(" · ")}</small></div>
                      <strong>{Math.round(match.confidence * 100)}%</strong>
                    </article>
                  ))}
                </div>
              )}

              {!!result.reverse_image_matches.length && (
                <div className="image-match-list">
                  <h4>Web copies</h4>
                  {result.reverse_image_matches.slice(0, 12).map((match, index) => (
                    <article key={index}>
                      <div>
                        <b>{match.domain || "web match"}</b>
                        <small>{match.backlinks?.[0] || match.image_url || "sem backlink"}</small>
                      </div>
                      <strong>{typeof match.score === "number" ? match.score.toFixed(1) : "—"}</strong>
                    </article>
                  ))}
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
