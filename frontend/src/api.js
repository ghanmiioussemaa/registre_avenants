// Client HTTP centralisé pour l'API Flask du tableau de bord.
// Chemins relatifs ("/api/...") : proxiés vers Flask en dev (voir vite.config.js),
// servis directement par Flask en prod (build React copié dans frontend/dist).

async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    let detail = null;
    try {
      detail = await res.json();
    } catch {
      // pas de corps JSON (ex: erreur réseau) : on ignore
    }
    const message = (detail && (detail.error || detail.message)) || `Erreur ${res.status}`;
    const err = new Error(message);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  return res;
}

export const api = {
  getStats: () => request("/stats"),
  getTypes: () => request("/types"),

  getAvenants: (params = {}) => {
    const qs = new URLSearchParams();
    if (params.statut) qs.set("statut", params.statut);
    if (params.type) qs.set("type", params.type);
    if (params.q) qs.set("q", params.q);
    if (params.avecContrat) qs.set("avec_contrat", "1");
    const query = qs.toString();
    return request(`/avenants${query ? `?${query}` : ""}`);
  },
  getAvenant: (messageId) => request(`/avenants/${encodeURIComponent(messageId)}`),
  deleteAvenant: (messageId) =>
    request(`/avenants/${encodeURIComponent(messageId)}`, { method: "DELETE" }),
  avenantPdfUrl: (messageId) => `/api/avenants/${encodeURIComponent(messageId)}/pdf`,
  avenantJsonUrl: (messageId) => `/api/avenants/${encodeURIComponent(messageId)}/json`,
  avenantDocumentUrl: (messageId, filename) =>
    `/api/avenants/${encodeURIComponent(messageId)}/documents/${encodeURIComponent(filename)}`,

  getContracts: () => request("/contrats"),
  getContract: (contractId) => request(`/contrats/${encodeURIComponent(contractId)}`),
  deleteHistory: (contractId, historyId) =>
    request(`/contrats/${encodeURIComponent(contractId)}/historique/${historyId}`, {
      method: "DELETE",
    }),

  lancerAgent: () => request("/agent/lancer", { method: "POST" }),
  getAgentStatus: () => request("/agent/status"),
  getAgentLog: () => request("/agent/log"),
};
