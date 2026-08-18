import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useFlash } from "../FlashContext.jsx";
import { useRefresh } from "../RefreshContext.jsx";
import StampBadge from "../components/StampBadge.jsx";
import ErrorPage from "./ErrorPage.jsx";
import { formatDateTime, formatPercent } from "../format.js";

const IMAGE_EXT = ["jpg", "jpeg", "png", "gif", "webp", "bmp", "heic"];

function fileExt(name = "") {
  const m = /\.([a-z0-9]+)$/i.exec(name || "");
  return m ? m[1].toLowerCase() : "";
}

function fileKind(name = "") {
  const ext = fileExt(name);
  if (IMAGE_EXT.includes(ext)) return "image";
  if (ext === "pdf") return "pdf";
  return "generic";
}

export default function AvenantDetail() {
  const { messageId } = useParams();
  const [a, setA] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const { refreshKey, bump } = useRefresh();
  const flash = useFlash();
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    api
      .getAvenant(messageId)
      .then((data) => !cancelled && setA(data))
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
  }, [messageId, refreshKey]);

  async function handleDelete() {
    if (!window.confirm("Supprimer définitivement cet avenant de l'historique ? Cette action est irréversible.")) {
      return;
    }
    try {
      const res = await api.deleteAvenant(messageId);
      flash(res.message, "success");
      bump();
      navigate("/avenants");
    } catch (err) {
      flash(err.message, "warning");
    }
  }

  if (notFound) return <ErrorPage message="Introuvable." />;
  if (loading && !a) return <div className="empty-state">Chargement...</div>;
  if (!a) return null;

  const report = a.report || {};
  const details = report?.donnees?.details_modification || {};
  const contrat = report?.validation_rapport?.contrat_en_base;
  const docs = report?.documents_joints || [];

  return (
    <>
      <div className="page-header">
        <div>
          <p className="page-eyebrow">
            <Link to="/avenants">← Avenants</Link> · {a.type_avenant || "Type non classé"}
          </p>
          <h1 className="page-title">{a.subject || "(sans objet)"}</h1>
        </div>
        <div style={{ textAlign: "right" }}>
          <StampBadge ok={a.conforme} />
          <div style={{ marginTop: 10, display: "flex", gap: 8, justifyContent: "flex-end" }}>
            {a.pdf_exists ? (
              <a className="btn small" href={api.avenantPdfUrl(a.message_id)}>
                Télécharger le PDF
              </a>
            ) : (
              <span className="btn small outline" style={{ opacity: 0.5, cursor: "default" }}>
                PDF indisponible
              </span>
            )}
            {a.json_exists && (
              <a className="btn small outline" href={api.avenantJsonUrl(a.message_id)}>
                JSON brut
              </a>
            )}
            <button type="button" className="btn small danger outline" onClick={handleDelete}>
              Supprimer
            </button>
          </div>
        </div>
      </div>

      <div className="two-col">
        <div>
          <div className="card">
            <p className="card-label">Message</p>
            <div className="kv">
              <b>Expéditeur</b>
              <span>{a.sender || "—"}</span>
              <b>Reçu le</b>
              <span>{formatDateTime(a.date_received)}</span>
              <b>Confiance IA</b>
              <span>{formatPercent(a.confidence)}</span>
              <b>ID message</b>
              <span className="mono small">{a.message_id}</span>
            </div>
          </div>

          <div className="card">
            <p className="card-label">Résumé</p>
            <p style={{ margin: 0, fontSize: "13.5px", lineHeight: 1.6 }}>
              {a.resume || "Aucun résumé disponible."}
            </p>
          </div>

          <div className="card">
            <p className="card-label">Données extraites</p>
            <div className="kv">
              <b>N° contrat</b>
              <span className="mono">{a.numero_contrat || "—"}</span>
              <b>Client</b>
              <span>{a.nom_client || "—"}</span>
            </div>
            {Object.keys(details).length > 0 && (
              <>
                <p className="card-label" style={{ marginTop: 14 }}>
                  Modification demandée
                </p>
                <div className="kv">
                  {Object.entries(details).map(([k, v]) => (
                    <React.Fragment key={k}>
                      <b>{k}</b>
                      <span>{v || "—"}</span>
                    </React.Fragment>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        <div>
          <div className="card">
            <p className="card-label">Rapport de validation</p>
            {a.conforme ? (
              <p className="small" style={{ color: "var(--stamp-green)" }}>
                Toutes les règles métier et documents requis sont vérifiés.
              </p>
            ) : (
              <>
                {a.erreurs_regles_metier && a.erreurs_regles_metier.length > 0 && (
                  <>
                    <p className="small muted" style={{ marginBottom: 6 }}>
                      Contrôles échoués :
                    </p>
                    <ul className="error-list">
                      {a.erreurs_regles_metier.map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  </>
                )}
                {a.documents_manquants && a.documents_manquants.length > 0 && (
                  <>
                    <p className="small muted" style={{ margin: "10px 0 6px" }}>
                      Documents manquants :
                    </p>
                    <ul className="error-list">
                      {a.documents_manquants.map((d, i) => (
                        <li key={i}>{d}</li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            )}
          </div>

          <div className="card">
            <p className="card-label">Contrat en base</p>
            {contrat ? (
              <>
                <div className="kv">
                  <b>N° contrat</b>
                  <span className="mono">{contrat.contract_number}</span>
                  <b>Souscripteur</b>
                  <span>{contrat.subscriber_name}</span>
                  <b>Email</b>
                  <span>{contrat.email || "—"}</span>
                  <b>Statut</b>
                  <span>{contrat.status || "—"}</span>
                </div>
                <Link className="btn small outline" style={{ marginTop: 12 }} to={`/contrats/${contrat.id}`}>
                  Voir la fiche contrat →
                </Link>
              </>
            ) : (
              <div className="empty-state" style={{ padding: "16px 0" }}>
                Aucun contrat trouvé en base pour ce message.
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <p className="card-label">Pièces jointes analysées</p>
        {docs.length > 0 ? (
          <div className="doc-grid">
            {docs.map((doc, i) => {
              const infos = doc.informations_extraites || {};
              const kind = fileKind(doc.nom_fichier);
              const ext = fileExt(doc.nom_fichier);
              const url = doc.nom_fichier ? api.avenantDocumentUrl(a.message_id, doc.nom_fichier) : null;
              return (
                <div className="doc-card" key={i}>
                  <div className={`doc-preview ${kind}`}>
                    {url && ext && (
                      <span className="doc-format-tag">{ext}</span>
                    )}
                    {kind === "image" && url ? (
                      <img src={url} alt={doc.nom_fichier} loading="lazy" />
                    ) : kind === "pdf" ? (
                      <div className="doc-icon">PDF</div>
                    ) : (
                      <div className="doc-icon">{ext || "FILE"}</div>
                    )}
                  </div>
                  <div className="doc-body">
                    <div className="doc-card-title">{doc.type_document || "Document"}</div>
                    <div className="muted small" style={{ marginBottom: 6, wordBreak: "break-word" }}>
                      {doc.nom_fichier}
                    </div>
                    {doc.description && <div className="doc-field">{doc.description}</div>}
                    {infos.nom_complet && (
                      <div className="doc-field">
                        <b>Nom lu :</b> {infos.nom_complet}
                      </div>
                    )}
                    {infos.numero_cin && (
                      <div className="doc-field">
                        <b>N° CIN :</b> {infos.numero_cin}
                      </div>
                    )}
                    {infos.date_validite && (
                      <div className="doc-field">
                        <b>Validité :</b> {infos.date_validite}
                      </div>
                    )}
                    {url && (
                      <a className="doc-open-link" href={url} target="_blank" rel="noreferrer">
                        Ouvrir dans son format d'origine →
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="empty-state">Aucune pièce jointe analysée.</div>
        )}
      </div>
    </>
  );
}
