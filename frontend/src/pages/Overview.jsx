import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useFlash } from "../FlashContext.jsx";
import { useRefresh } from "../RefreshContext.jsx";
import { useAgentStatus, isTakingTooLong } from "../useAgentStatus.js";
import PipelineTracker from "../components/PipelineTracker.jsx";
import StampBadge from "../components/StampBadge.jsx";
import StatusPill from "../components/StatusPill.jsx";
import { formatDateTime } from "../format.js";

export default function Overview() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [launching, setLaunching] = useState(false);
  const { refreshKey, bump } = useRefresh();
  const flash = useFlash();
  const navigate = useNavigate();

  const agentStatus = useAgentStatus({
    onJustFinished: (data) => {
      flash(
        data.state === "error" ? `Erreur : ${data.error}` : data.message || "Traitement terminé.",
        data.state === "error" ? "warning" : "success"
      );
      setTimeout(bump, 300);
    },
  });
  const running = agentStatus.state === "running";

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

  let agentMessage = agentStatus.message || "";
  if (running && isTakingTooLong(agentStatus.started_at)) {
    agentMessage =
      "Cela prend plus de temps que d'habitude — vérifiez EMAIL_ADDRESS/EMAIL_PASSWORD/IMAP_SERVER dans .env, ou consultez logs/app.log directement.";
  } else if (!running && agentStatus.error) {
    agentMessage = `Erreur : ${agentStatus.error}`;
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getStats()
      .then((data) => !cancelled && setStats(data))
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return (
    <>
      <div className="page-header">
        <div>
          <p className="page-eyebrow">Tableau de bord</p>
          <h1 className="page-title">Vue d'ensemble</h1>
        </div>
        <button type="button" className="btn" disabled={running || launching} onClick={handleLancer}>
          {running ? "⏳ Traitement en cours..." : "▶ Lancer le traitement des e-mails"}
        </button>
      </div>

      <div className="card" id="agent-panel">
        <p className="card-label">Agent — pipeline en direct</p>
        <div className="agent-status-row">
          <StatusPill state={agentStatus.state} />
          {running && (
            <span className="mono small" style={{ color: "var(--accent)" }}>
              ⏱ {agentStatus.elapsedSeconds}s écoulées
            </span>
          )}
          <span className="small muted">{agentMessage || "En attente d'un lancement."}</span>
        </div>
        <PipelineTracker pipeline={agentStatus.pipeline} running={running} />
      </div>

      {error && <div className="flash warning">{error}</div>}
      {loading && !stats ? (
        <div className="empty-state">Chargement...</div>
      ) : (
        stats && (
          <>
            <div className="stat-grid">
              <div className="stat">
                <div className="stat-value">{stats.total}</div>
                <div className="stat-label">Avenants traités</div>
              </div>
              <div className="stat green">
                <div className="stat-value">{stats.conformes}</div>
                <div className="stat-label">Dossiers conformes</div>
              </div>
              <div className="stat red">
                <div className="stat-value">{stats.rejetes}</div>
                <div className="stat-label">Dossiers rejetés</div>
              </div>
              <div className="stat brass">
                <div className="stat-value">{stats.taux_conformite}%</div>
                <div className="stat-label">Taux de conformité</div>
              </div>
            </div>

            <div className="card">
              <p className="card-label">Répartition par type d'avenant</p>
              {stats.par_type && Object.keys(stats.par_type).length > 0 ? (
                Object.entries(stats.par_type).map(([typeName, d]) => (
                  <div className="bar-row" key={typeName}>
                    <div className="small">{typeName}</div>
                    <div className="bar-track">
                      {d.total > 0 && (
                        <>
                          <div
                            className="bar-fill-ok"
                            style={{ width: `${Math.round((d.conformes / d.total) * 1000) / 10}%` }}
                          />
                          <div
                            className="bar-fill-ko"
                            style={{ width: `${Math.round((d.rejetes / d.total) * 1000) / 10}%` }}
                          />
                        </>
                      )}
                    </div>
                    <div className="small mono">
                      {d.conformes}/{d.total}
                    </div>
                  </div>
                ))
              ) : (
                <div className="empty-state">
                  Aucun avenant traité pour l'instant. Lancez l'agent pour commencer à peupler ce
                  registre.
                </div>
              )}
            </div>

            <div className="card">
              <p className="card-label">Derniers avenants traités</p>
              {stats.derniers && stats.derniers.length > 0 ? (
                <table>
                  <thead>
                    <tr>
                      <th>Reçu le</th>
                      <th>Expéditeur</th>
                      <th>Type</th>
                      <th>Contrat</th>
                      <th>Statut</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.derniers.map((a) => (
                      <tr
                        className="row-link"
                        key={a.message_id}
                        onClick={() => navigate(`/avenants/${encodeURIComponent(a.message_id)}`)}
                      >
                        <td className="mono small">{formatDateTime(a.date_received)}</td>
                        <td>{a.sender || "—"}</td>
                        <td>{a.type_avenant || "—"}</td>
                        <td className="mono">{a.numero_contrat || "—"}</td>
                        <td>
                          <StampBadge ok={a.conforme} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="empty-state">Rien à afficher pour le moment.</div>
              )}
            </div>
          </>
        )
      )}
    </>
  );
}
