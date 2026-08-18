import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";

const LABELS = { idle: "Inactif", running: "En cours...", done: "Terminé", error: "Erreur" };
const SEUIL_ALERTE_SECONDES = 180; // au-delà, on prévient que ça semble anormalement long

export function statusLabel(state) {
  return LABELS[state] || state;
}

/**
 * Interroge périodiquement /api/agent/status et appelle onJustFinished()
 * quand un traitement lancé pendant la consultation vient de se terminer
 * (jamais au tout premier chargement de la page).
 */
export function useAgentStatus({ intervalMs = 4000, runningIntervalMs = 1000, onJustFinished } = {}) {
  const [status, setStatus] = useState({
    state: "idle",
    message: null,
    error: null,
    started_at: null,
    pipeline: null,
  });
  const [now, setNow] = useState(Date.now());
  const lastState = useRef(null);

  useEffect(() => {
    let cancelled = false;
    let id = null;

    async function poll() {
      try {
        const data = await api.getAgentStatus();
        if (cancelled) return;
        setStatus(data);
        if (lastState.current === "running" && (data.state === "done" || data.state === "error")) {
          onJustFinished && onJustFinished(data);
        }
        lastState.current = data.state;
        // Bascule dynamiquement la cadence de rafraîchissement : rapide (1s)
        // pendant un traitement, plus espacée sinon.
        const nextDelay = data.state === "running" ? runningIntervalMs : intervalMs;
        if (!cancelled) {
          clearTimeout(id);
          id = setTimeout(poll, nextDelay);
        }
      } catch {
        if (!cancelled) {
          clearTimeout(id);
          id = setTimeout(poll, intervalMs);
        }
      }
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, runningIntervalMs]);

  // Horloge indépendante du polling : fait défiler le compteur seconde par
  // seconde pendant que l'agent tourne, pour un suivi vraiment en direct.
  useEffect(() => {
    if (status.state !== "running") return undefined;
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(tick);
  }, [status.state]);

  const elapsedSeconds = status.started_at
    ? Math.max(0, Math.floor((now - new Date(status.started_at).getTime()) / 1000))
    : 0;

  return { ...status, elapsedSeconds };
}

/**
 * Suit le journal de l'agent (logs/app.log) seconde par seconde tant que le
 * traitement est en cours, pour un affichage "live" des étapes en coulisses.
 */
export function useAgentLog({ active = false, intervalMs = 1000 } = {}) {
  const [log, setLog] = useState("");

  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;

    async function poll() {
      try {
        const data = await api.getAgentLog();
        if (!cancelled) setLog(data.log || "");
      } catch {
        // on retentera au prochain tick
      }
    }

    poll();
    const id = setInterval(poll, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [active, intervalMs]);

  return log;
}

export function elapsedLabel(startedAt) {
  if (!startedAt) return "";
  const secs = Math.max(0, Math.round((Date.now() - new Date(startedAt).getTime()) / 1000));
  return `depuis ${secs}s`;
}

export function isTakingTooLong(startedAt) {
  if (!startedAt) return false;
  const secs = Math.max(0, Math.round((Date.now() - new Date(startedAt).getTime()) / 1000));
  return secs > SEUIL_ALERTE_SECONDES;
}
