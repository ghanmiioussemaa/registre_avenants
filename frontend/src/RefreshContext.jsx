import React, { createContext, useContext, useState, useCallback } from "react";

const RefreshContext = createContext(null);

// Incrémenté à chaque fin de traitement agent (done/error) ; les pages qui
// affichent des données issues de la base (stats, avenants, contrats) le
// mettent dans leurs dépendances useEffect pour se recharger automatiquement,
// exactement comme le rechargement de page (location.reload()) de la version
// Jinja d'origine.
export function RefreshProvider({ children }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const bump = useCallback(() => setRefreshKey((k) => k + 1), []);
  return <RefreshContext.Provider value={{ refreshKey, bump }}>{children}</RefreshContext.Provider>;
}

export function useRefresh() {
  const ctx = useContext(RefreshContext);
  if (!ctx) throw new Error("useRefresh doit être utilisé dans un RefreshProvider");
  return ctx;
}
