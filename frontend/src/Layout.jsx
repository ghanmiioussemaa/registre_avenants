import React, { useCallback } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./components/Sidebar.jsx";
import FlashMessages from "./components/FlashMessages.jsx";
import { useFlash } from "./FlashContext.jsx";
import { useRefresh } from "./RefreshContext.jsx";

export default function Layout() {
  const flash = useFlash();
  const { bump } = useRefresh();

  const handleAgentFinished = useCallback(
    (data) => {
      // Le traitement vient de se terminer : on prévient l'utilisateur et on
      // déclenche le rafraîchissement des données affichées (stats, listes...),
      // à la manière du location.reload() de la version d'origine.
      if (data.state === "error") {
        flash(data.error ? `Erreur : ${data.error}` : "Le traitement a échoué.", "warning");
      } else {
        flash(data.message || "Traitement terminé.", "success");
      }
      setTimeout(bump, 300);
    },
    [flash, bump]
  );

  return (
    <div className="layout">
      <Sidebar onAgentFinished={handleAgentFinished} />
      <main className="main">
        <FlashMessages />
        <Outlet />
      </main>
    </div>
  );
}
