"""
API du tableau de bord (backend Flask) de l'agent de traitement des avenants.

Lecture seule : cette API ne fait qu'exposer en JSON ce que l'agent (app.py) a déjà
traité et enregistré (MySQL + rapports PDF/JSON dans data/). Elle ne relance pas
la boîte mail et n'applique aucune règle métier elle-même.

Le frontend est une application React séparée (voir ../../frontend) qui consomme
cette API. En développement, lancer les deux :
    Terminal 1 : cd agent1 && python dashboard/dashboard_app.py   (API sur :5050)
    Terminal 2 : cd frontend && npm run dev                       (React sur :5173)

En production, `npm run build` génère frontend/dist, servi automatiquement par
cette API si le dossier est présent (voir la fin du fichier).
"""

import os
import sys
import logging
from decimal import Decimal

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, send_file, jsonify, send_from_directory
from flask_cors import CORS
import mysql.connector

import data as dash_data  # module local dashboard/data.py
import agent_runner  # module local dashboard/agent_runner.py (pilotage du pipeline en arrière-plan)
from storage.file_manager import FileManager
from config import ATTACHMENT_FOLDER

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MailAI.dashboard")

FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend", "dist")
FRONTEND_DIST = os.path.abspath(FRONTEND_DIST)

app = Flask(__name__, static_folder=FRONTEND_DIST if os.path.isdir(FRONTEND_DIST) else None)
app.secret_key = os.getenv("DASHBOARD_SECRET_KEY", "dev-only-change-me")

# En dev, le frontend (Vite, http://localhost:5173) et l'API (http://localhost:5050)
# tournent sur deux ports différents : CORS est nécessaire. En prod (fichiers React
# servis directement par Flask), ça reste inoffensif.
CORS(app, resources={r"/api/*": {"origins": "*"}})

AVENANT_TYPES = [
    "Changement adresse",
    "Changement RIB",
    "Changement nom",
    "Correction informations personnelles",
]


def serialize_avenant(a: dict) -> dict:
    """Convertit un avenant (dict Python, dates incluses) en JSON-safe."""
    out = dict(a)
    for key in ("date_received", "created_at"):
        if out.get(key) is not None and hasattr(out[key], "isoformat"):
            out[key] = out[key].isoformat()
    out.pop("pdf_path", None)
    out.pop("json_path", None)
    return out


def serialize_contract(c: dict) -> dict:
    out = dict(c)
    for key in ("effective_date", "creation_date"):
        if out.get(key) is not None and hasattr(out[key], "isoformat"):
            out[key] = out[key].isoformat()
    if isinstance(out.get("premium_amount"), (int, float, Decimal)):
        out["premium_amount"] = float(out["premium_amount"])
    return out


def serialize_history(h: dict) -> dict:
    out = dict(h)
    if out.get("created_at") is not None and hasattr(out["created_at"], "isoformat"):
        out["created_at"] = out["created_at"].isoformat()
    out.pop("pdf_path", None)
    out.pop("json_path", None)
    return out


@app.errorhandler(mysql.connector.Error)
def handle_db_error(err):
    logger.error(f"Erreur MySQL : {err}")
    return jsonify(error="Impossible de joindre la base de données de l'agent.", detail=str(err)), 500


@app.errorhandler(Exception)
def handle_unexpected_error(err):
    """Filet de sécurité : toute erreur non prévue renvoie du JSON (pas une page HTML),
    pour que le frontend React puisse toujours afficher un message au lieu de planter
    silencieusement (page blanche)."""
    if request.path.startswith("/api/"):
        logger.exception("Erreur inattendue")
        return jsonify(error="Erreur inattendue côté serveur.", detail=str(err)), 500
    raise err


# ---------------------------------------------------------------------------
# Agent (pipeline mail -> LLM -> règles métier -> DB/PDF)
# ---------------------------------------------------------------------------

@app.route("/api/agent/lancer", methods=["POST"])
def lancer_agent():
    """Déclenche le pipeline en arrière-plan."""
    started = agent_runner.start_agent()
    if started:
        return jsonify(ok=True, message="Traitement des e-mails lancé en arrière-plan...")
    return jsonify(ok=False, message="Un traitement est déjà en cours, merci de patienter."), 409


@app.route("/api/agent/status")
def agent_status_api():
    """Statut courant de l'agent (polling front-end), pour un suivi en direct."""
    return jsonify(agent_runner.get_status())


@app.route("/api/agent/log")
def agent_log_api():
    """Dernières lignes du journal de l'agent, pour un suivi seconde par seconde."""
    return jsonify(log=agent_runner.tail_log(120))


# ---------------------------------------------------------------------------
# Vue d'ensemble
# ---------------------------------------------------------------------------

@app.route("/api/stats")
def stats_api():
    stats = dash_data.get_stats()
    stats["derniers"] = [serialize_avenant(a) for a in stats["derniers"]]
    return jsonify(stats)


@app.route("/api/types")
def types_api():
    return jsonify(AVENANT_TYPES)


# ---------------------------------------------------------------------------
# Avenants
# ---------------------------------------------------------------------------

@app.route("/api/avenants")
def avenants_list_api():
    statut = request.args.get("statut", "tous")
    type_avenant = request.args.get("type", "tous")
    recherche = request.args.get("q", "")
    avec_contrat_uniquement = request.args.get("avec_contrat") == "1"
    avenants = dash_data.list_avenants(
        statut=statut,
        type_avenant=type_avenant,
        recherche=recherche,
        avec_contrat_uniquement=avec_contrat_uniquement,
    )
    return jsonify([serialize_avenant(a) for a in avenants])


@app.route("/api/avenants/<path:message_id>")
def avenant_detail_api(message_id):
    avenant = dash_data.get_avenant(message_id)
    if not avenant:
        return jsonify(error="Introuvable."), 404
    return jsonify(serialize_avenant(avenant))


@app.route("/api/avenants/<path:message_id>/pdf")
def avenant_pdf(message_id):
    avenant = dash_data.get_avenant(message_id)
    if not avenant:
        return jsonify(error="Introuvable."), 404
    if not avenant["pdf_exists"]:
        return jsonify(error="Le rapport PDF n'est pas encore disponible pour ce dossier."), 404
    return send_file(avenant["pdf_path"], as_attachment=True)


@app.route("/api/avenants/<path:message_id>/json")
def avenant_json(message_id):
    avenant = dash_data.get_avenant(message_id)
    if not avenant:
        return jsonify(error="Introuvable."), 404
    if not avenant["json_exists"]:
        return jsonify(error="Le rapport JSON n'est pas encore disponible pour ce dossier."), 404
    return send_file(avenant["json_path"], as_attachment=True, mimetype="application/json")


@app.route("/api/avenants/<path:message_id>/documents/<path:filename>")
def avenant_document(message_id, filename):
    """Sert une pièce jointe telle qu'elle a été reçue (PDF, image, ...) pour
    un aperçu dans son format d'origine, plutôt qu'un simple nom de fichier."""
    safe_id = FileManager.sanitize_filename(message_id)
    directory = os.path.abspath(os.path.join(ATTACHMENT_FOLDER, safe_id))
    full_path = os.path.abspath(os.path.join(directory, filename))
    if not full_path.startswith(directory + os.sep):
        return jsonify(error="Chemin invalide."), 400
    if not os.path.isfile(full_path):
        return jsonify(error="Pièce jointe introuvable."), 404
    return send_from_directory(directory, os.path.basename(full_path))


@app.route("/api/avenants/<path:message_id>", methods=["DELETE"])
def avenant_delete(message_id):
    """Supprime définitivement un avenant du registre (ligne + fichiers PDF/JSON/eml associés)."""
    ok = dash_data.delete_avenant(message_id)
    if ok:
        return jsonify(ok=True, message="Avenant supprimé de l'historique.")
    return jsonify(ok=False, message="Impossible de supprimer cet avenant (introuvable)."), 404


# ---------------------------------------------------------------------------
# Contrats
# ---------------------------------------------------------------------------

@app.route("/api/contrats")
def contracts_list_api():
    contracts = dash_data.list_contracts()
    return jsonify([serialize_contract(c) for c in contracts])


@app.route("/api/contrats/<contract_id>")
def contract_detail_api(contract_id):
    contract = dash_data.get_contract_with_history(contract_id)
    if not contract:
        return jsonify(error="Introuvable."), 404
    contract = serialize_contract(contract)
    contract["history"] = [serialize_history(h) for h in contract.get("history", [])]
    return jsonify(contract)


@app.route("/api/contrats/<contract_id>/historique/<int:history_id>", methods=["DELETE"])
def avenant_history_delete(contract_id, history_id):
    """Supprime une ligne précise de l'historique des avenants d'un contrat."""
    ok = dash_data.delete_avenant_history(history_id)
    if ok:
        return jsonify(ok=True, message="Ligne d'historique supprimée.")
    return jsonify(ok=False, message="Impossible de supprimer cette ligne d'historique."), 404


# ---------------------------------------------------------------------------
# Fichiers statiques du frontend React compilé (production uniquement)
# ---------------------------------------------------------------------------

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    if not app.static_folder or not os.path.isdir(app.static_folder):
        return jsonify(
            message="API du tableau de bord des avenants. Le frontend React n'est pas compilé "
                    "(lancez 'npm run build' dans frontend/, ou 'npm run dev' en développement).",
        )
    full_path = os.path.join(app.static_folder, path)
    if path and os.path.isfile(full_path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return jsonify(error="Introuvable."), 404
    return serve_react("")


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
