import React from "react";
import { Link } from "react-router-dom";

export default function ErrorPage({ message = "Introuvable.", detail = null }) {
  return (
    <>
      <div className="page-header">
        <div>
          <p className="page-eyebrow">Erreur</p>
          <h1 className="page-title">{message}</h1>
        </div>
      </div>
      {detail && (
        <div className="card">
          <p className="mono small">{detail}</p>
        </div>
      )}
      <Link className="btn outline" to="/">
        ← Retour à l'accueil
      </Link>
    </>
  );
}
