import React from "react";

// Doit rester synchronisé avec PIPELINE_STEPS côté backend
// (backend/dashboard/agent_runner.py).
const STEPS = [
  { id: "connexion", label: "Connexion boîte mail", icon: "📡" },
  { id: "recuperation", label: "Récupération des e-mails", icon: "📥" },
  { id: "analyse_mail", label: "Analyse du mail", icon: "✉️" },
  { id: "pieces_jointes", label: "Pièces jointes", icon: "📎" },
  { id: "ia", label: "Analyse IA", icon: "🧠" },
  { id: "regles_metier", label: "Règles métier", icon: "📋" },
  { id: "enregistrement", label: "Enregistrement", icon: "💾" },
  { id: "maj_contrat", label: "Mise à jour contrat", icon: "🗂️" },
];

export default function PipelineTracker({ pipeline, running }) {
  const steps = pipeline?.steps || {};
  const currentId = pipeline?.current;

  return (
    <div className="pipeline">
      <div className="pipeline-track">
        {STEPS.map((step, i) => {
          const state = steps[step.id] || "pending";
          const isLast = i === STEPS.length - 1;
          return (
            <React.Fragment key={step.id}>
              <div className={`pipeline-step ${state}`}>
                <div className="pipeline-step-icon">
                  {state === "done" ? "✓" : step.icon}
                </div>
                <div className="pipeline-step-label">{step.label}</div>
              </div>
              {!isLast && <div className={`pipeline-connector ${state === "done" ? "done" : ""}`} />}
            </React.Fragment>
          );
        })}
      </div>

      {running && (
        <div className="pipeline-meta">
          {pipeline?.mail_total != null && (
            <span className="pipeline-meta-item">
              Mail <b>{Math.max(pipeline.mail_index, pipeline.mail_total ? 1 : 0)}</b>
              {pipeline.mail_total ? ` / ${pipeline.mail_total}` : ""}
            </span>
          )}
          {pipeline?.current_subject && (
            <span className="pipeline-meta-item muted">« {pipeline.current_subject} »</span>
          )}
          {currentId && (
            <span className="pipeline-meta-item accent">
              {STEPS.find((s) => s.id === currentId)?.label || "En cours..."}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
