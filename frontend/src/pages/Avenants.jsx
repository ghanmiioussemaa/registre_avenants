import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { useFlash } from "../FlashContext.jsx";
import { useRefresh } from "../RefreshContext.jsx";
import StampBadge from "../components/StampBadge.jsx";
import { formatDateTime } from "../format.js";

export default function Avenants() {
  const [searchParams, setSearchParams] = useSearchParams();
  const statut = searchParams.get("statut") || "tous";
  const typeAvenant = searchParams.get("type") || "tous";
  const recherche = searchParams.get("q") || "";
  const avecContrat = searchParams.get("avec_contrat") === "1";

  const [avenants, setAvenants] = useState([]);
  const [types, setTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const { refreshKey, bump } = useRefresh();
  const flash = useFlash();
  const navigate = useNavigate();

  useEffect(() => {
    api.getTypes().then(setTypes).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getAvenants({ statut, type: typeAvenant, q: recherche, avecContrat })
      .then((data) => !cancelled && setAvenants(data))
      .catch((err) => !cancelled && flash(err.message, "warning"))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statut, typeAvenant, recherche, avecContrat, refreshKey]);

  function handleFilterSubmit(e) {
    e.preventDefault();
    const form = new FormData(e.target);
    const next = new URLSearchParams();
    next.set("statut", form.get("statut"));
    next.set("type", form.get("type"));
    if (form.get("q")) next.set("q", form.get("q"));
    if (form.get("avec_contrat")) next.set("avec_contrat", "1");
    setSearchParams(next);
  }

  async function handleDelete(e, messageId) {
    e.stopPropagation();
    if (!window.confirm("Supprimer définitivement cet avenant de l'historique ? Cette action est irréversible.")) {
      return;
    }
    try {
      const res = await api.deleteAvenant(messageId);
      flash(res.message, "success");
      bump();
    } catch (err) {
      flash(err.message, "warning");
    }
  }

  return (
    <>
      <div className="page-header">
        <div>
          <p className="page-eyebrow">
            {avenants.length} dossier{avenants.length !== 1 ? "s" : ""}
          </p>
          <h1 className="page-title">Avenants</h1>
        </div>
      </div>

      <form className="filters" onSubmit={handleFilterSubmit}>
        <select name="statut" defaultValue={statut} key={`statut-${statut}`}>
          <option value="tous">Tous les statuts</option>
          <option value="conforme">Conformes</option>
          <option value="rejete">Rejetés</option>
        </select>
        <select name="type" defaultValue={typeAvenant} key={`type-${typeAvenant}`}>
          <option value="tous">Tous les types</option>
          {types.map((t) => (
            <option value={t} key={t}>
              {t}
            </option>
          ))}
        </select>
        <input type="text" name="q" placeholder="Rechercher (nom, contrat, sujet...)" defaultValue={recherche} />
        <label className="small" style={{ display: "flex", alignItems: "center", gap: 6, whiteSpace: "nowrap" }}>
          <input type="checkbox" name="avec_contrat" value="1" defaultChecked={avecContrat} />
          Avec numéro de contrat uniquement
        </label>
        <button type="submit">Filtrer</button>
      </form>

      <div className="card" style={{ padding: 0 }}>
        {loading ? (
          <div className="empty-state">Chargement...</div>
        ) : avenants.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>Reçu le</th>
                <th>Expéditeur</th>
                <th>Type</th>
                <th>Contrat</th>
                <th>Client</th>
                <th>Statut</th>
                <th>Rapport</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {avenants.map((a) => (
                <tr
                  className="row-link"
                  key={a.message_id}
                  onClick={() => navigate(`/avenants/${encodeURIComponent(a.message_id)}`)}
                >
                  <td className="mono small">{formatDateTime(a.date_received)}</td>
                  <td>{a.sender || "—"}</td>
                  <td>{a.type_avenant || "—"}</td>
                  <td className="mono">{a.numero_contrat || "—"}</td>
                  <td>{a.nom_client || "—"}</td>
                  <td>
                    <StampBadge ok={a.conforme} />
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    {a.pdf_exists ? (
                      <a className="btn small outline" href={api.avenantPdfUrl(a.message_id)}>
                        PDF
                      </a>
                    ) : (
                      <span className="muted small">—</span>
                    )}
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      className="btn small danger outline"
                      onClick={(e) => handleDelete(e, a.message_id)}
                    >
                      Supprimer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">Aucun avenant ne correspond à ces critères.</div>
        )}
      </div>
    </>
  );
}
