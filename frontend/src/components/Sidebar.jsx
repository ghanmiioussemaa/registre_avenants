import React, { useCallback, useState } from "react";
import { NavLink } from "react-router-dom";
import { api } from "../api.js";
import { useFlash } from "../FlashContext.jsx";
import { useAgentStatus } from "../useAgentStatus.js";
import StatusPill from "./StatusPill.jsx";

export default function Sidebar({ onAgentFinished }) {
  const flash = useFlash();
  const [launching, setLaunching] = useState(false);

  const handleFinished = useCallback(
    (data) => {
      onAgentFinished && onAgentFinished(data);
    },
    [onAgentFinished]
  );

  const status = useAgentStatus({ onJustFinished: handleFinished });

  async function handleLancer() {
    setLaunching(true);
    try {
      const res = await api.lancerAgent();
      flash(res.message, "success");
    } catch (err) {
      flash(err.message, "warning");
    } finally {
      setLaunching(false);
    }
  }

  const running = status.state === "running";

  return (
    <aside className="sidebar">
      <div className="brand">
        Registre des
        <br />
        avenants
      </div>
      <div className="brand-sub">Agent IA · Contrats</div>

      <NavLink to="/" end className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
        <span className="dot" /> Vue d'ensemble
      </NavLink>
      <NavLink to="/avenants" className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
        <span className="dot" /> Avenants
      </NavLink>
      <NavLink to="/contrats" className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
        <span className="dot" /> Contrats
      </NavLink>

      <div className="sidebar-agent">
        <div className="agent-status-row">
          <StatusPill state={status.state} />
        </div>
        {running && (
          <div className="agent-clock">
            Suivi en direct · <span className="tick">{status.elapsedSeconds}s</span>
          </div>
        )}
        <button
          type="button"
          className="btn small"
          style={{ width: "100%" }}
          disabled={running || launching}
          onClick={handleLancer}
        >
          {running ? `⏳ En cours... (${status.elapsedSeconds}s)` : "▶ Lancer l'agent"}
        </button>
      </div>

      <div className="sidebar-foot">
        Agent IA connecté à la boîte mail, aux règles métier et à MySQL — le tableau se met à jour
        automatiquement après chaque traitement.
      </div>
    </aside>
  );
}
