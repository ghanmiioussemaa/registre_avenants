"""
Pilotage de l'agent (pipeline app.py) depuis le tableau de bord.

Ce module permet de déclencher `run_pipeline()` (le même code que `python app.py`)
en arrière-plan, depuis un clic dans le dashboard, sans bloquer le serveur Flask,
et expose un statut consultable (idle / running / done / error).

En plus du statut global, un `PipelineTrackingHandler` observe en silence les
messages du logger "MailAI" (déjà utilisés par app.py) et les fait correspondre
aux grandes étapes métier du pipeline (connexion, analyse du mail, pièces
jointes, IA, règles métier, enregistrement, mise à jour du contrat...). Cela
permet au frontend d'afficher un vrai suivi visuel étape par étape, seconde
par seconde, plutôt qu'un flux de logs bruts.
"""

import os
import re
import sys
import threading
import logging
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("MailAI.dashboard.agent_runner")

_lock = threading.Lock()

# Étapes métier du pipeline (voir backend/app.py::run_pipeline), dans l'ordre.
# "match" liste des extraits de messages logger.info() qui signalent le passage
# à cette étape (voir les appels logger.info(...) correspondants dans app.py).
PIPELINE_STEPS = [
    {"id": "connexion", "label": "Connexion à la boîte mail",
     "match": ["Démarrage du traitement automatique"]},
    {"id": "recuperation", "label": "Récupération des e-mails non lus",
     "match": ["mails non lus trouvés", "Aucun nouvel e-mail"]},
    {"id": "analyse_mail", "label": "Analyse du mail en cours",
     "match": ["--- Analyse du mail ID"]},
    {"id": "pieces_jointes", "label": "Lecture des pièces jointes",
     "match": ["Extraction du texte du PDF", "Extraction OCR", "Pièce jointe non standard"]},
    {"id": "ia", "label": "Analyse IA (extraction structurée)",
     "match": ["Interrogation de Groq"]},
    {"id": "regles_metier", "label": "Vérification des règles métier",
     "match": ["Documents joints détectés", "Documents manquants calculés", "Rapport de validation"]},
    {"id": "enregistrement", "label": "Enregistrement (JSON / PDF / base)",
     "match": ["sauvegarde JSON", "enregistrées avec succès dans MySQL", "Rapport PDF généré"]},
    {"id": "maj_contrat", "label": "Mise à jour du contrat",
     "match": ["impact sur le contrat", "Avenant appliqué et historisé", "Avenant rejeté historisé"]},
    {"id": "termine", "label": "Session terminée",
     "match": ["Session de traitement terminée"]},
]

_STEP_IDS = [s["id"] for s in PIPELINE_STEPS]


def _fresh_pipeline() -> dict:
    return {
        "current": None,
        "steps": {s["id"]: "pending" for s in PIPELINE_STEPS},
        "mail_index": 0,
        "mail_total": None,
        "current_subject": None,
    }


_status = {
    "state": "idle",  # idle | running | done | error
    "started_at": None,
    "finished_at": None,
    "error": None,
    "message": None,
    "pipeline": _fresh_pipeline(),
}


def get_status() -> dict:
    """Copie thread-safe du statut courant (avec l'état du pipeline)."""
    with _lock:
        out = dict(_status)
        out["pipeline"] = {
            **_status["pipeline"],
            "steps": dict(_status["pipeline"]["steps"]),
        }
        return out


def _advance_pipeline(pipeline: dict, step_id: str) -> None:
    """Marque toutes les étapes précédentes comme terminées et celle-ci comme active."""
    if step_id not in _STEP_IDS:
        return
    target_index = _STEP_IDS.index(step_id)
    for i, sid in enumerate(_STEP_IDS):
        if i < target_index:
            pipeline["steps"][sid] = "done"
        elif i == target_index:
            pipeline["steps"][sid] = "done" if sid == "termine" else "active"
        # les étapes suivantes restent inchangées (pending, ou déjà vues sur un mail précédent)
    pipeline["current"] = step_id


class PipelineTrackingHandler(logging.Handler):
    """Traduit les logs texte de app.py en progression structurée du pipeline."""

    def emit(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            return
        with _lock:
            if _status["state"] != "running":
                return
            pipeline = _status["pipeline"]

            for step in PIPELINE_STEPS:
                if any(marker in msg for marker in step["match"]):
                    if step["id"] == "analyse_mail":
                        # Nouveau mail : les étapes propres au traitement d'un
                        # message (pièces jointes -> maj contrat) redeviennent
                        # "en attente" pour ce nouveau mail, sans réinitialiser
                        # tout le pipeline.
                        for sid in _STEP_IDS[_STEP_IDS.index("pieces_jointes"):_STEP_IDS.index("termine")]:
                            pipeline["steps"][sid] = "pending"
                    _advance_pipeline(pipeline, step["id"])
                    break

            if "--- Analyse du mail ID" in msg:
                pipeline["mail_index"] += 1

            m = re.search(r"Sujet\s*:\s*(.+)", msg)
            if m:
                pipeline["current_subject"] = m.group(1).strip()

            m = re.search(r"(\d+)\s+mails non lus trouvés", msg)
            if m:
                pipeline["mail_total"] = int(m.group(1))


_pipeline_handler = PipelineTrackingHandler()
_pipeline_handler.setLevel(logging.INFO)
logging.getLogger("MailAI").addHandler(_pipeline_handler)


def _count_avenants() -> int:
    """Nombre total d'avenants déjà enregistrés (pour calculer le delta après un run)."""
    try:
        import data as dash_data  # module local dashboard/data.py
        return len(dash_data.list_avenants())
    except Exception:
        return -1


def _run():
    global _status
    avant = _count_avenants()
    with _lock:
        _status.update(
            state="running",
            started_at=datetime.now().isoformat(timespec="seconds"),
            finished_at=None,
            error=None,
            message="Connexion à la boîte mail et traitement en cours...",
            pipeline=_fresh_pipeline(),
        )
    try:
        from app import run_pipeline  # même fonction que `python app.py`
        run_pipeline()
        apres = _count_avenants()
        if avant >= 0 and apres >= 0:
            nouveaux = apres - avant
            message = (
                f"{nouveaux} nouvel(le)(s) avenant(s) enregistré(s)."
                if nouveaux > 0
                else "Terminé : aucun nouvel avenant détecté sur cette session."
            )
        else:
            message = "Traitement terminé."
        with _lock:
            _status["pipeline"]["current"] = "termine"
            for sid in _STEP_IDS:
                _status["pipeline"]["steps"][sid] = "done"
            _status.update(
                state="done",
                finished_at=datetime.now().isoformat(timespec="seconds"),
                message=message,
            )
    except Exception as e:
        logger.exception("Erreur lors de l'exécution de l'agent depuis le dashboard")
        with _lock:
            _status.update(
                state="error",
                finished_at=datetime.now().isoformat(timespec="seconds"),
                error=str(e),
                message="Le traitement a échoué, voir le détail de l'erreur.",
            )


def start_agent() -> bool:
    """Démarre l'agent dans un thread si aucun traitement n'est déjà en cours."""
    with _lock:
        if _status["state"] == "running":
            return False
    t = threading.Thread(target=_run, name="agent-pipeline", daemon=True)
    t.start()
    return True


def tail_log(n_lines: int = 60) -> str:
    """Dernières lignes du journal de l'agent (logs/app.log). Conservé pour debug
    avancé, mais le frontend affiche désormais le pipeline structuré par défaut."""
    try:
        from config import LOG_FOLDER
        path = os.path.join(LOG_FOLDER, "app.log")
        if not os.path.isfile(path):
            return ""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-n_lines:])
    except Exception as e:
        return f"[Impossible de lire le journal : {e}]"
