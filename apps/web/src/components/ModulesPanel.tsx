import { Boxes, CircleCheck, CircleOff } from "lucide-react";
import { ModuleInfo } from "../api";

export default function ModulesPanel({ modules }: { modules: ModuleInfo[] }) {
  return (
    <div className="module-grid expanded">
      {modules.map((module) => (
        <article className="module" key={module.id}>
          <div className="module-icon"><Boxes size={18} /></div>
          <div className="module-copy">
            <h3>{module.name}</h3>
            <p>{module.description || module.id}</p>
            <code>{module.id}</code>
          </div>
          <span className="mode">{module.mode}</span>
          <span className={module.available ? "available" : "offline"}>
            {module.available ? <CircleCheck size={11} /> : <CircleOff size={11} />}
            {module.available ? "ready" : "roadmap"}
          </span>
        </article>
      ))}
    </div>
  );
}
