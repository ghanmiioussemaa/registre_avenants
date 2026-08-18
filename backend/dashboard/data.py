"""
Couche d'accès aux données pour le tableau de bord.
Lit directement les mêmes tables MySQL que l'agent (analyzed_emails, contracts,
avenant_history) et localise les rapports PDF/JSON déjà générés sur disque,
sans jamais dupliquer la logique métier de l'agent (aucune règle métier ici).
"""

import os
import sys
import json
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from config import MYSQL_CONFIG, JSON_FOLDER, PDF_FOLDER, EMAIL_FOLDER
from storage.file_manager import FileManager
from storage.contract_manager import ContractManager

logger = logging.getLogger("MailAI.dashboard")


def get_connection():
    """Ouvre une connexion MySQL en réutilisant la config existante de l'agent."""
    return mysql.connector.connect(**MYSQL_CONFIG)


def _parse_report(raw_report):
    """Le champ intelligence_report est stocké en JSON texte (ou déjà un dict selon le driver)."""
    if raw_report is None:
        return {}
    if isinstance(raw_report, dict):
        return raw_report
    try:
        return json.loads(raw_report)
    except (TypeError, json.JSONDecodeError):
        return {}


def _report_paths(message_id: str) -> dict:
    """Retourne les chemins (et leur existence) des fichiers PDF/JSON associés à un message."""
    pdf_path = FileManager.get_pdf_report_path(message_id)
    safe_id = FileManager.sanitize_filename(message_id)
    json_path = os.path.join(JSON_FOLDER, f"{safe_id}.json")
    return {
        "pdf_path": pdf_path,
        "pdf_exists": os.path.isfile(pdf_path),
        "json_path": json_path,
        "json_exists": os.path.isfile(json_path),
    }


def _row_to_avenant(row: dict) -> dict:
    """Aplati une ligne 'analyzed_emails' + son rapport JSON en un dict prêt pour les templates."""
    report = _parse_report(row.get("intelligence_report"))
    validation = report.get("validation_rapport", {}) or {}
    donnees = report.get("donnees", {}) or {}
    contrat_en_base = validation.get("contrat_en_base") or {}

    # Le numéro de contrat "officiel" est celui du contrat réellement retrouvé en
    # base (par numéro de contrat OU par e-mail expéditeur) : c'est plus fiable
    # que le seul texte brut extrait par l'IA, qui peut être absent/mal lu même
    # quand le contrat a bien été identifié et l'avenant traité normalement.
    numero_contrat = contrat_en_base.get("contract_number") or donnees.get("numero_contrat")
    nom_client = donnees.get("nom_client") or contrat_en_base.get("subscriber_name")

    return {
        "message_id": row.get("message_id"),
        "subject": row.get("subject"),
        "sender": row.get("sender"),
        "date_received": row.get("date_received"),
        "created_at": row.get("created_at"),
        "type_avenant": report.get("type_avenant"),
        "confidence": report.get("confidence"),
        "resume": report.get("resume"),
        "numero_contrat": numero_contrat,
        "nom_client": nom_client,
        # Le rapport (PDF + JSON) est TOUJOURS généré par l'agent, que le dossier soit
        # conforme ou rejeté : le statut n'affecte donc jamais la disponibilité du rapport.
        "conforme": bool(validation.get("conforme")),
        "raison_non_conformite": validation.get("raison_non_conformite"),
        "erreurs_regles_metier": validation.get("erreurs_regles_metier") or [],
        "documents_manquants": validation.get("documents_manquants") or [],
        "report": report,
        **_report_paths(row.get("message_id")),
    }


def list_avenants(statut: str = "tous", type_avenant: str = "tous", recherche: str = "", avec_contrat_uniquement: bool = False) -> list:
    """Liste tous les avenants traités, du plus récent au plus ancien, avec filtres optionnels."""
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT message_id, subject, sender, date_received, intelligence_report, created_at
            FROM analyzed_emails
            ORDER BY COALESCE(date_received, created_at) DESC
            """
        )
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    avenants = [_row_to_avenant(r) for r in rows]

    # Par défaut, TOUS les avenants traités par le backend sont affichés (même
    # ceux sans contrat retrouvé en base), pour que le registre reflète fidèlement
    # ce que l'agent a réellement détecté. Le filtre "avec numéro de contrat
    # uniquement" est disponible en option (case à cocher) plutôt qu'imposé, pour
    # éviter de masquer silencieusement des avenants réellement traités.
    if avec_contrat_uniquement:
        avenants = [a for a in avenants if a["numero_contrat"]]

    if statut == "conforme":
        avenants = [a for a in avenants if a["conforme"]]
    elif statut == "rejete":
        avenants = [a for a in avenants if not a["conforme"]]

    if type_avenant and type_avenant != "tous":
        avenants = [a for a in avenants if a["type_avenant"] == type_avenant]

    if recherche:
        q = recherche.strip().lower()
        avenants = [
            a for a in avenants
            if q in (a["subject"] or "").lower()
            or q in (a["sender"] or "").lower()
            or q in (a["numero_contrat"] or "").lower()
            or q in (a["nom_client"] or "").lower()
        ]

    return avenants


def get_avenant(message_id: str) -> dict:
    """Récupère un avenant précis par son message_id."""
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT message_id, subject, sender, date_received, intelligence_report, created_at
            FROM analyzed_emails
            WHERE message_id = %s
            LIMIT 1
            """,
            (message_id,),
        )
        row = cur.fetchone()
        cur.close()
    finally:
        conn.close()

    if not row:
        return {}
    return _row_to_avenant(row)


def delete_avenant(message_id: str) -> bool:
    """
    Supprime définitivement un avenant de l'historique : la ligne correspondante
    dans `analyzed_emails`, ainsi que les fichiers associés (PDF, JSON, .eml)
    sur disque s'ils existent. Suppression best-effort sur les fichiers : une
    erreur de suppression de fichier n'empêche pas la suppression en base.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM analyzed_emails WHERE message_id = %s", (message_id,))
        conn.commit()
        deleted = cur.rowcount > 0
        cur.close()
    finally:
        conn.close()

    safe_id = FileManager.sanitize_filename(message_id)
    fichiers = [
        FileManager.get_pdf_report_path(message_id),
        os.path.join(JSON_FOLDER, f"{safe_id}.json"),
        os.path.join(EMAIL_FOLDER, f"{safe_id}.eml"),
    ]
    for path in fichiers:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError as e:
            logger.warning(f"Impossible de supprimer le fichier {path} : {e}")

    return deleted


def delete_avenant_history(history_id: int) -> bool:
    """Supprime une ligne précise de l'historique des avenants d'un contrat (table avenant_history)."""
    return ContractManager.delete_avenant_history(history_id)


def get_stats() -> dict:
    """Statistiques globales pour la vue d'ensemble."""
    avenants = list_avenants()
    total = len(avenants)
    conformes = sum(1 for a in avenants if a["conforme"])
    rejetes = total - conformes

    par_type = {}
    for a in avenants:
        t = a["type_avenant"] or "Non classé"
        par_type.setdefault(t, {"total": 0, "conformes": 0, "rejetes": 0})
        par_type[t]["total"] += 1
        if a["conforme"]:
            par_type[t]["conformes"] += 1
        else:
            par_type[t]["rejetes"] += 1

    taux = round((conformes / total) * 100, 1) if total else 0.0

    return {
        "total": total,
        "conformes": conformes,
        "rejetes": rejetes,
        "taux_conformite": taux,
        "par_type": par_type,
        "derniers": avenants[:8],
    }


def list_contracts() -> list:
    """Liste tous les contrats en base."""
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT id, contract_number, subscriber_name, email, phone, address,
                   iban, account_holder, cin_number, status, is_active,
                   premium_amount, premium_paid, effective_date, creation_date
            FROM contracts
            ORDER BY contract_number ASC
            """
        )
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        conn.close()


def get_contract_with_history(contract_id: str) -> dict:
    """Détail d'un contrat + son historique d'avenants (table avenant_history)."""
    contract = ContractManager.get_contract_by_id(contract_id)
    if not contract:
        return {}
    history = ContractManager.get_avenant_history(contract.get("id"))
    for h in history:
        errors = h.get("validation_errors")
        if isinstance(errors, str):
            try:
                h["validation_errors"] = json.loads(errors)
            except (TypeError, json.JSONDecodeError):
                h["validation_errors"] = [errors] if errors else []
        elif errors is None:
            h["validation_errors"] = []
        # Lignes historiques créées avant l'ajout de message_id : pas de rapport
        # disponible (ni PDF ni JSON), on ne masque pas l'erreur, on l'indique.
        if h.get("message_id"):
            h.update(_report_paths(h["message_id"]))
        else:
            h["pdf_exists"] = False
            h["json_exists"] = False
    contract["history"] = history
    return contract
