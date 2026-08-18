import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useFlash } from "../FlashContext.jsx";
import { useRefresh } from "../RefreshContext.jsx";
import StampBadge from "../components/StampBadge.jsx";
import ErrorPage from "./ErrorPage.jsx";
import { formatDateTime, formatMoney } from "../format.js";

export default function ContractDetail() {
  const { contractId } = useParams();
  const [c, setC] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const { refreshKey, bump } = useRefresh();
  const flash = useFlash();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    api
      .getContract(contractId)
      .then((data) => !cancelled && setC(data))
      .catch((err) => {
        if (cancelled) return;
        if (err.status === 404) setNotFound(true);
        else flash(err.message, "warning");
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contractId, refreshKey]);

  async function handleDeleteHistory(historyId) {
    if (
      !window.confirm(
        "Supprimer définitivement cette ligne de l'historique ? Cette action est irréversible."
      )
    ) {
      return;
    }
    try {
      const res = await api.deleteHistory(contractId, historyId);
      flash(res.message, "success");
      bump();
    } catch (err) {
      flash(err.message, "warning");
    }
  }

  if (notFound) return <ErrorPage message="Introuvable." />;
  if (loading && !c) return <div className="empty-state">Chargement...</div>;
  if (!c) return null;

  return (
    <>
      <div className="page-header">
        <div>
          <p className="page-eyebrow">
            <Link to="/contrats">← Contrats</Link>
          </p>
          <h1 className="page-title">{c.contract_number}</h1>
        </div>
        <StampBadge ok={c.is_active} okLabel="Actif" koLabel="Inactif" />
      </div>

      <div className="two-col">
        <div className="card">
          <p className="card-label">Souscripteur</p>
          <div className="kv">
            <b>Nom</b>
            <span>{c.subscriber_name}</span>
            <b>Email</b>
            <span>{c.email || "—"}</span>
            <b>Téléphone</b>
            <span>{c.phone || "—"}</span>
            <b>Adresse</b>
            <span>{c.address || "—"}</span>
            <b>N° CIN</b>
            <span className="mono">{c.cin_number || "—"}</span>
          </div>
        </div>

        <div className="card">
          <p className="card-label">Contrat</p>
          <div className="kv">
            <b>IBAN</b>
            <span className="mono small">{c.iban || "—"}</span>
            <b>Titulaire compte</b>
            <span>{c.account_holder || "—"}</span>
            <b>Prime</b>
            <span>{formatMoney(c.premium_amount)}</span>
            <b>Prime payée</b>
            <span>{c.premium_paid ? "Oui" : "Non"}</span>
            <b>Date d'effet</b>
            <span>{c.effective_date || "—"}</span>
          </div>
        </div>
      </div>

      <div className="card">
        <p className="card-label">Historique des avenants</p>
        {c.history && c.history.length > 0 ? (
          c.history.map((h) => (
            <div className="history-item" key={h.id}>
              <div style={{ minWidth: 110 }}>
                <StampBadge ok={h.status === "validé"} okLabel="Validé" koLabel="Rejeté" />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: "13.5px" }}>{h.avenant_type}</div>
                <div className="mono small muted">{formatDateTime(h.created_at)}</div>
                {h.validation_errors && h.validation_errors.length > 0 && (
                  <ul className="error-list" style={{ marginTop: 6 }}>
                    {h.validation_errors.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                )}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                {h.pdf_exists ? (
                  <a className="btn small outline" href={api.avenantPdfUrl(h.message_id)}>
                    PDF
                  </a>
                ) : (
                  <span className="muted small">PDF indisponible</span>
                )}
                <button
                  type="button"
                  className="btn small danger outline"
                  onClick={() => handleDeleteHistory(h.id)}
                >
                  Supprimer
                </button>
              </div>
            </div>
          ))
        ) : (
          <div className="empty-state">Aucun avenant enregistré pour ce contrat.</div>
        )}
      </div>
    </>
  );
}
