import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useFlash } from "../FlashContext.jsx";
import { useRefresh } from "../RefreshContext.jsx";
import StampBadge from "../components/StampBadge.jsx";
import { formatMoney } from "../format.js";

export default function Contracts() {
  const [contracts, setContracts] = useState([]);
  const [loading, setLoading] = useState(true);
  const { refreshKey } = useRefresh();
  const flash = useFlash();
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getContracts()
      .then((data) => !cancelled && setContracts(data))
      .catch((err) => !cancelled && flash(err.message, "warning"))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  return (
    <>
      <div className="page-header">
        <div>
          <p className="page-eyebrow">
            {contracts.length} contrat{contracts.length !== 1 ? "s" : ""}
          </p>
          <h1 className="page-title">Contrats</h1>
        </div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {loading ? (
          <div className="empty-state">Chargement...</div>
        ) : contracts.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>N° contrat</th>
                <th>Souscripteur</th>
                <th>Email</th>
                <th>Statut</th>
                <th>Prime</th>
              </tr>
            </thead>
            <tbody>
              {contracts.map((c) => (
                <tr className="row-link" key={c.id} onClick={() => navigate(`/contrats/${c.id}`)}>
                  <td className="mono">{c.contract_number}</td>
                  <td>{c.subscriber_name}</td>
                  <td className="small">{c.email || "—"}</td>
                  <td>
                    <StampBadge ok={c.is_active} okLabel="Actif" koLabel="Inactif" />
                  </td>
                  <td className="mono small">{c.premium_amount != null ? c.premium_amount.toFixed(2) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">Aucun contrat en base.</div>
        )}
      </div>
    </>
  );
}
