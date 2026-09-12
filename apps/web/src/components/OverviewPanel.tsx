import {
  ArrowRight, CheckCircle2, Clock3, Database, FileSearch, Image as ImageIcon,
  Lightbulb, Network, Play, ShieldCheck, Sparkles
} from "lucide-react";
import { Workspace } from "../api";

function confidenceLabel(value: number) {
  if (value >= 0.85) return "muito forte";
  if (value >= 0.65) return "forte";
  if (value >= 0.35) return "plausível";
  return "fraco";
}

export default function OverviewPanel({
  workspace,
  running,
  onRun,
  onOpenTab
}: {
  workspace: Workspace;
  running: boolean;
  onRun: () => void;
  onOpenTab: (tab: "graph" | "evidence" | "image" | "analysis" | "report") => void;
}) {
  const graph = workspace.graph;
  const topFindings = [...graph.findings]
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 4);

  const strongEdges = graph.edges.filter((edge) => edge.confidence >= 0.65);
  const needsWork = graph.evidence.length === 0 || graph.entities.length <= 1;
  const imageCount = graph.entities.filter((entity) => entity.kind === "image").length;

  const nextSteps: Array<{
    title: string;
    text: string;
    action: string;
    tab?: "graph" | "evidence" | "image" | "analysis" | "report";
    run?: boolean;
  }> = [];

  if (!graph.evidence.length) {
    nextSteps.push({
      title: "Rode a primeira coleta",
      text: "O VIGIL consulta as fontes públicas disponíveis para esse tipo de alvo e registra de onde cada resultado veio.",
      action: "Investigar agora",
      run: true
    });
  } else {
    nextSteps.push({
      title: "Revise as conexões",
      text: "Veja o que está conectado, o nível de confiança e a evidência que justifica cada relação.",
      action: "Abrir conexões",
      tab: "graph"
    });
  }

  if (!imageCount) {
    nextSteps.push({
      title: "Tem uma imagem?",
      text: "Adicione uma foto ou screenshot para analisar metadata, hashes e reutilizações da mesma imagem.",
      action: "Analisar imagem",
      tab: "image"
    });
  }

  if (graph.evidence.length) {
    nextSteps.push({
      title: "Confira as fontes",
      text: "Antes de aceitar qualquer conclusão, abra as evidências e valide a origem dos dados.",
      action: "Ver evidências",
      tab: "evidence"
    });
  }

  if (graph.findings.length || graph.edges.length) {
    nextSteps.push({
      title: "Monte sua conclusão",
      text: "Registre hipóteses, contrapontos e depois gere um relatório rastreável.",
      action: "Abrir análise",
      tab: "analysis"
    });
  }

  return (
    <div className="overview">
      <section className="overview-hero">
        <div>
          <span className="eyebrow">investigation overview</span>
          <h2>O que o VIGIL sabe até agora</h2>
          <p>
            Aqui você vê o resultado sem precisar entender ferramentas de OSINT.
            O VIGIL separa <b>o que foi observado</b> de <b>o que foi inferido</b>.
          </p>
        </div>

        <button className="primary overview-run" onClick={onRun} disabled={running}>
          <Play size={16} />
          {running ? "investigando…" : graph.evidence.length ? "investigar novamente" : "começar investigação"}
        </button>
      </section>

      <section className="plain-stats">
        <article>
          <span className="plain-stat-icon"><Network size={18} /></span>
          <div><b>{graph.entities.length}</b><small>itens encontrados</small></div>
        </article>
        <article>
          <span className="plain-stat-icon"><CheckCircle2 size={18} /></span>
          <div><b>{strongEdges.length}</b><small>conexões fortes</small></div>
        </article>
        <article>
          <span className="plain-stat-icon"><Database size={18} /></span>
          <div><b>{graph.evidence.length}</b><small>fontes registradas</small></div>
        </article>
        <article>
          <span className="plain-stat-icon"><FileSearch size={18} /></span>
          <div><b>{graph.findings.length}</b><small>achados analíticos</small></div>
        </article>
      </section>

      {needsWork && (
        <section className="explain-card">
          <Sparkles size={20} />
          <div>
            <b>Comece pelo botão “começar investigação”</b>
            <p>
              Você não precisa escolher ferramentas. O VIGIL decide quais módulos públicos
              fazem sentido para o alvo e mostra o que conseguiu e o que não conseguiu consultar.
            </p>
          </div>
        </section>
      )}

      <div className="overview-columns">
        <section className="overview-card">
          <div className="overview-card-head">
            <div>
              <span className="eyebrow">findings</span>
              <h3>Principais achados</h3>
            </div>
            {!!topFindings.length && (
              <button className="text-action" onClick={() => onOpenTab("analysis")}>
                analisar <ArrowRight size={13} />
              </button>
            )}
          </div>

          {!topFindings.length ? (
            <div className="friendly-empty">
              <Lightbulb size={22} />
              <b>Ainda não há conclusões</b>
              <p>Isso é normal antes da primeira coleta. Achados só aparecem quando existe evidência suficiente.</p>
            </div>
          ) : (
            <div className="plain-findings">
              {topFindings.map((finding) => (
                <article key={finding.id}>
                  <div className="finding-signal">
                    <span className={"severity " + finding.severity}>{finding.severity}</span>
                    <small>{confidenceLabel(finding.confidence)} · {Math.round(finding.confidence * 100)}%</small>
                  </div>
                  <b>{finding.title}</b>
                  <p>{finding.summary}</p>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="overview-card">
          <div className="overview-card-head">
            <div>
              <span className="eyebrow">next actions</span>
              <h3>O que fazer agora</h3>
            </div>
          </div>

          <div className="next-step-list">
            {nextSteps.slice(0, 4).map((step) => (
              <article key={step.title}>
                <span className="step-dot" />
                <div>
                  <b>{step.title}</b>
                  <p>{step.text}</p>
                  <button
                    onClick={() => step.run ? onRun() : step.tab && onOpenTab(step.tab)}
                    disabled={step.run && running}
                  >
                    {step.action} <ArrowRight size={12} />
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>

      <section className="method-strip">
        <ShieldCheck size={18} />
        <div>
          <b>Como interpretar o resultado</b>
          <span>Observado = veio diretamente de uma fonte pública.</span>
          <span>Inferido = relação calculada e acompanhada de confiança + justificativa.</span>
          <span>Não encontrado = não significa que não exista.</span>
        </div>
        <Clock3 size={16} />
      </section>
    </div>
  );
}
