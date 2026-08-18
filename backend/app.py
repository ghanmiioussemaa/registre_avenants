import os
import json
import logging
import re
import sys
from decimal import Decimal
from datetime import date, datetime

# Assure que Python trouve les dossiers locaux peu importe d'où le script est lancé
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mail.downloader import MailDownloader
from mail.parser import MailParser
from mail.attachment import AttachmentProcessor
from llm.extractor import GroqExtractor
from storage.file_manager import FileManager
from storage.db import DatabaseManager
from storage.report_generator import ReportGenerator
from config import LOG_FOLDER
from business_rules_engine import BusinessRulesEngine
from mail.mailer import (
    MailSender,
    extract_email_address,
    build_missing_info_email,
    build_validated_email,
)

# Configuration de la journalisation (Logs)
#
# IMPORTANT : on n'utilise PAS logging.basicConfig() ici. Cette fonction ne fait
# STRICTEMENT RIEN si le root logger a déjà des handlers -- or, quand ce pipeline
# est lancé depuis le dashboard (dashboard_app.py appelle déjà logging.basicConfig()
# à son propre démarrage, puis importe app.run_pipeline() à la demande), le root
# logger est déjà configuré au moment où ce fichier est importé. Résultat : le
# FileHandler vers logs/app.log n'était jamais attaché dans ce cas précis, et le
# panneau de suivi en direct du dashboard (qui lit logs/app.log) restait vide
# pendant et après toute analyse lancée depuis l'interface web.
#
# On attache donc les handlers directement sur le logger "MailAI" (et pas sur le
# root logger), et on protège contre les doublons si run_pipeline() est appelé
# plusieurs fois dans le même processus (ex: plusieurs clics sur "Lancer l'agent").
logger = logging.getLogger("MailAI")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    _file_handler = logging.FileHandler(os.path.join(LOG_FOLDER, "app.log"), encoding="utf-8")
    _file_handler.setFormatter(_formatter)
    logger.addHandler(_file_handler)

    _stream_handler = logging.StreamHandler()
    _stream_handler.setFormatter(_formatter)
    logger.addHandler(_stream_handler)

    # Évite que les messages remontent en plus vers le root logger (qui pourrait
    # déjà avoir son propre handler console via le dashboard) et s'y affichent en double.
    logger.propagate = False

def normalize_document_type_label(label: str) -> str:
    """Normalise les libellés de type de document pour comparer correctement les variantes."""
    if not label:
        return ""

    normalized = label.strip().lower()
    synonyms = {
        "carte d'identité": ["carte nationale d'identité", "carte d'identité", "cni", "cin", "numéro d'identité", "pièce d'identité", "identité"],
        "rib/iban": ["rib", "iban", "bic", "swift", "banque", "relevé bancaire"],
        "justificatif de domicile": ["justificatif de domicile", "facture", "edf", "quittance", "domicile", "adresse", "preuve d'adresse"],
        "permis de conduire": ["permis", "permis de conduire", "conduire"],
        "contrat": ["contrat", "avenant", "contrat d'assurance"],
        "carte grise": ["carte grise", "immatriculation", "plaque"],
        "attestation": ["attestation", "attestation d'assurance", "attestation de domicile"],
        "formulaire de demande": ["formulaire", "formulaire de demande", "demande signée", "formulaire de changement"],
    }

    for canonical, variants in synonyms.items():
        if any(term in normalized for term in variants):
            return canonical

    return label.strip()


def infer_missing_documents(type_avenant: str, documents_joints: list, rules_engine: BusinessRulesEngine = None) -> list:
    """Retourne les documents manquants attendus selon le type d'avenant."""
    
    # Utiliser le moteur de règles si disponible
    if rules_engine:
        avenant_config = rules_engine.get_avenant_requirements(type_avenant)
        if avenant_config:
            required_docs = avenant_config.get("documents", [])
            present_types = {
                normalize_document_type_label(doc.get("type_document"))
                for doc in documents_joints
                if isinstance(doc, dict) and doc.get("type_document")
            }
            
            required_normalized = {
                normalize_document_type_label(doc_type)
                for doc_type in required_docs
            }
            
            return [doc for doc in required_docs if normalize_document_type_label(doc) not in present_types]
    
    # Fallback sur la structure codée en dur (rétro-compatibilité)
    required_by_type = {
        "Changement adresse": ["Justificatif de domicile", "Carte d'identité"],
        "Changement RIB": ["RIB/IBAN", "Mandat SEPA signé", "Carte d'identité"],
        "Changement nom": ["Carte d'identité", "Justificatif de changement de nom"],
        "Correction informations personnelles": ["Carte d'identité"]
    }

    if not type_avenant or type_avenant not in required_by_type:
        return []

    present_types = {
        normalize_document_type_label(doc.get("type_document"))
        for doc in documents_joints
        if isinstance(doc, dict) and doc.get("type_document")
    }

    required_normalized = {
        normalize_document_type_label(doc_type)
        for doc_type in required_by_type[type_avenant]
    }

    return [doc for doc in required_by_type[type_avenant] if normalize_document_type_label(doc) not in present_types]


def is_avenant_mail(analysis_dict: dict) -> bool:
    """Retourne True si l'analyse indique clairement un avenant d'assurance."""
    value = analysis_dict.get("is_avenant")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "oui", "y"}
    return bool(value)


def infer_document_type_from_filename_or_content(filename: str, content: str) -> str:
    filename_lower = (filename or "").lower()
    content_lower = (content or "").lower()

    if "carte" in filename_lower and ("ident" in filename_lower or "cin" in filename_lower or "id" in filename_lower):
        return "Carte d'identité"
    if "rib" in filename_lower or "iban" in filename_lower or "banque" in filename_lower or "bic" in filename_lower or "swift" in filename_lower:
        return "RIB/IBAN"
    if "domicile" in filename_lower or "facture" in filename_lower or "edf" in filename_lower or "quittance" in filename_lower:
        return "Justificatif de domicile"
    if "permis" in filename_lower or "conduire" in filename_lower:
        return "Permis de conduire"
    if "contrat" in filename_lower:
        return "Contrat"
    if "grise" in filename_lower:
        return "Carte grise"
    if "attestation" in filename_lower:
        return "Attestation d'assurance"
    if "mandat" in filename_lower or "sepa" in filename_lower:
        return "Mandat SEPA signé"
    if any(term in content_lower for term in ["carte nationale d'identité", "cin", "numéro d'identité", "date de naissance"]):
        return "Carte d'identité"
    if any(term in content_lower for term in ["rib", "iban", "bic", "swift"]):
        return "RIB/IBAN"
    if any(term in content_lower for term in ["facture", "edf", "quittance", "domicile", "adresse"]):
        return "Justificatif de domicile"
    if any(term in content_lower for term in ["permis", "conduire"]):
        return "Permis de conduire"
    if any(term in content_lower for term in ["contrat", "avenant"]):
        return "Contrat"

    return "Autre"

def sanitize_contract_data(contract_data: dict) -> dict:
    """Convertit les types renvoyés par MySQL non sérialisables en JSON (Decimal, date, datetime) en types simples."""
    if not contract_data:
        return {}
    sanitized = {}
    for key, value in contract_data.items():
        if isinstance(value, Decimal):
            sanitized[key] = float(value)
        elif isinstance(value, (datetime, date)):
            sanitized[key] = value.isoformat()
        else:
            sanitized[key] = value
    return sanitized


def find_identity_document(documents_joints: list) -> dict:
    """Retrouve, parmi les documents joints, celui identifié comme une pièce d'identité (CIN/CNI/passeport)."""
    for doc in documents_joints or []:
        if not isinstance(doc, dict):
            continue
        type_doc = (doc.get("type_document") or "").lower()
        if any(kw in type_doc for kw in ("carte d'identité", "carte nationale d'identité", "cin", "cni", "passeport")):
            return doc
    return {}


def extract_cin_from_document(doc: dict) -> str:
    """Lit le numéro de CIN dans les informations_extraites d'un document d'identité (repli regex sur le texte brut)."""
    if not isinstance(doc, dict):
        return ""

    informations = doc.get("informations_extraites") or {}
    if isinstance(informations, dict):
        for key in ("numero_cin", "numero_cni", "numero_piece_identite", "numero_identite", "cin"):
            if informations.get(key):
                return str(informations[key]).strip()

    contenu = doc.get("contenu_brut") or ""
    match = re.search(r"(?:num[ée]ro\s*(?:cin|cni|d['’]identit[ée])?|cin)\s*:?\s*n?°?\s*([A-Za-z0-9]{5,15})", contenu, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def build_contract_update_payload(avenant_type: str, donnees_extraites: dict,
                                   documents_joints: list = None, contract_data: dict = None) -> dict:
    """
    Construit le dictionnaire des nouvelles valeurs à appliquer au contrat (table `contracts`),
    à partir des données extraites par le LLM (donnees_extraites.details_modification) et,
    lorsque pertinent, de la pièce d'identité jointe.
    """
    if not isinstance(donnees_extraites, dict):
        donnees_extraites = {}
    documents_joints = documents_joints or []
    contract_data = contract_data or {}

    details = donnees_extraites.get("details_modification", {})
    if not isinstance(details, dict):
        details = {}

    def find_value(*keywords):
        """Cherche dans details_modification une clé contenant un des mots-clés (insensible à la casse)."""
        for key, value in details.items():
            key_lower = (key or "").lower()
            if value and any(kw in key_lower for kw in keywords):
                return value
        return None

    payload = {}

    if avenant_type == "Changement adresse":
        nouvelle_adresse = find_value("adresse", "domicile")
        if nouvelle_adresse:
            payload["address"] = nouvelle_adresse

    elif avenant_type == "Changement RIB":
        nouveau_iban = find_value("iban", "rib")
        if nouveau_iban:
            payload["iban"] = nouveau_iban
        titulaire = find_value("titulaire", "holder")
        if titulaire:
            payload["account_holder"] = titulaire

    elif avenant_type in ("Changement nom", "Correction informations personnelles"):
        nouveau_nom = find_value("nom", "nom_complet") or donnees_extraites.get("nom_client")
        if nouveau_nom:
            payload["subscriber_name"] = nouveau_nom

    # Association automatique du numéro de CIN au contrat s'il est lisible sur le document fourni
    # et pas encore enregistré en base : cela permet aux prochains avenants de vérifier automatiquement
    # la cohérence entre l'identité de l'expéditeur et le contrat (voir BusinessRulesEngine._verify_identity_coherence).
    if not contract_data.get("cin_number"):
        cin_lu = extract_cin_from_document(find_identity_document(documents_joints))
        if cin_lu:
            payload["cin_number"] = cin_lu

    return payload


def log_contract_cross_check(contract_data: dict, donnees_extraites: dict, client_email: str) -> None:
    """Affiche les informations du contrat trouvé en base et les compare aux données extraites par le LLM."""
    if not contract_data:
        logger.warning(" Aucun contrat trouvé en base (ni par numéro de contrat, ni par e-mail expéditeur).")
        return

    logger.info(" ─── Contrat trouvé en base de données ───")
    champs_a_afficher = (
        "id", "contract_number", "subscriber_name", "email", "phone", "address",
        "iban", "account_holder", "cin_number", "status", "is_active", "premium_amount",
        "premium_paid", "driver_license_valid", "age", "effective_date"
    )
    for champ in champs_a_afficher:
        if champ in contract_data:
            logger.info(f"    {champ} : {contract_data.get(champ)}")

    # Comparaison entre les données du contrat (source de vérité en base)
    # et les informations extraites du mail/pièces jointes par le LLM.
    # NB : la comparaison bloquante du CIN (document vs base) est faite par
    # BusinessRulesEngine._verify_identity_coherence via les checks "Correspondance avec
    # le contrat" / "Vérification de l'identité" ; ce log ci-dessous n'est qu'informatif.
    donnees_extraites = donnees_extraites or {}
    nom_llm = donnees_extraites.get("nom_client")
    nom_db = contract_data.get("subscriber_name")
    if nom_llm and nom_db and nom_llm.strip().lower() != nom_db.strip().lower():
        logger.warning(f" Incohérence : nom extrait du mail ('{nom_llm}') ≠ titulaire du contrat en base ('{nom_db}').")

    if client_email and contract_data.get("email") and client_email.strip().lower() != str(contract_data.get("email", "")).strip().lower():
        logger.warning(f" Incohérence : e-mail expéditeur ('{client_email}') ≠ e-mail du contrat en base ('{contract_data.get('email')}').")


def run_pipeline():
    logger.info("Démarrage du traitement automatique des e-mails...")
    
    # Initialisation du moteur de règles métier
    rules_engine = BusinessRulesEngine("business_rules.json")
    logger.info(f"Moteur de règles métier chargé: {rules_engine.get_rules_summary()}")
    
    downloader = MailDownloader()
    extractor = GroqExtractor()
    
    try:
        downloader.connect()
        raw_emails = downloader.fetch_unread_emails()
        
        if not raw_emails:
            logger.info("Aucun nouvel e-mail à traiter.")
            return

        logger.info(f"{len(raw_emails)} mails non lus trouvés au total.")
        
        #  On inverse pour traiter du plus RÉCENT au plus ANCIEN, et on limite à 10
        raw_emails = raw_emails[::-1][:10]
        logger.info("Limitation du traitement aux 10 e-mails les plus récents (Sécurité Quota).")

        for tmp_id, raw_bytes in raw_emails:
            try:
                # 1. Analyse préliminaire & extraction des pièces jointes
                email_data = MailParser.parse_email_bytes(raw_bytes)
                msg_id = email_data["message_id"]
                logger.info(f"--- Analyse du mail ID : {msg_id} ---")
                logger.info(f"Sujet : {email_data['subject']}")
                
                # 2. Lecture directe du texte des PDF et images joints
                attachments_combined_text = ""
                extracted_files = {}
                extracted_metadata = {}
                extracted_paths = {}
                supported_image_exts = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif", ".webp", ".heic")

                for attachment in email_data.get("attachments", []):
                    filename = attachment.get("filename", "")
                    filename_lower = filename.lower()
                    extracted_text = ""
                    attachment_type = "Autre"
                    extracted_paths[filename] = attachment.get("local_path", "")

                    if filename_lower.endswith(".pdf"):
                        attachment_type = "PDF"
                        if os.path.exists(attachment.get("local_path", "")):
                            logger.info(f"Extraction du texte du PDF : {filename}")
                            extracted_text = AttachmentProcessor.extract_text_from_pdf(attachment["local_path"])

                    elif filename_lower.endswith(supported_image_exts):
                        attachment_type = "Image"
                        if os.path.exists(attachment.get("local_path", "")):
                            logger.info(f"Extraction OCR / LLM de l'image : {filename}")
                            image_analysis = AttachmentProcessor.analyze_image_attachment(attachment["local_path"], filename)
                            extracted_text = image_analysis.get("contenu_brut") or AttachmentProcessor.extract_text_from_image(attachment["local_path"])
                            if not extracted_text or extracted_text.startswith("[LLM visuel"):
                                extracted_text = f"[Image non traitée : {os.path.basename(attachment['local_path'])}]"
                            extracted_metadata[filename] = image_analysis

                    else:
                        attachment_type = os.path.splitext(filename_lower)[1] or "Inconnu"
                        extracted_text = f"[Aucun texte direct extrait du fichier '{filename}'. Type détecté : {attachment_type}.]"
                        logger.info(f"Pièce jointe non standard : {filename} ({attachment_type})")

                    attachments_combined_text += f"\n--- Pièce jointe: {filename} ({attachment_type}) ---\n{extracted_text}\n"
                    extracted_files[filename] = extracted_text

                # 3. Appel de l'IA (Groq) pour l'analyse
                logger.info("Interrogation de Groq pour analyse structurée...")
                json_string_response = extractor.analyze_email_context(email_data, attachments_combined_text)
                
                # Conversion du JSON de l'IA en dictionnaire Python
                analysis_dict = json.loads(json_string_response)

                documents_joints = analysis_dict.get("documents_joints")
                if not isinstance(documents_joints, list):
                    documents_joints = []
                analysis_dict["documents_joints"] = documents_joints

                existing_docs = {
                    (doc.get("nom_fichier") or doc.get("filename") or ""): doc
                    for doc in documents_joints if isinstance(doc, dict)
                }

                for filename, extracted_text in extracted_files.items():
                    image_analysis = extracted_metadata.get(filename, {})
                    if filename in existing_docs:
                        doc = existing_docs[filename]
                        doc["contenu_brut"] = extracted_text
                        doc["chemin_fichier"] = extracted_paths.get(filename, "")
                        current_type = (doc.get("type_document") or "").strip()
                        inferred_type = image_analysis.get("type_document") or infer_document_type_from_filename_or_content(filename, extracted_text)
                        if not current_type or current_type.lower() == "autre":
                            doc["type_document"] = inferred_type
                        doc["description"] = doc.get("description") or image_analysis.get("description") or f"Document analysé : {doc['type_document']}"
                        if image_analysis.get("informations_extraites"):
                            doc["informations_extraites"] = image_analysis["informations_extraites"]
                        logger.info(f" Contenu et type ajoutés pour le fichier existant {filename} : {doc['type_document']}")
                    else:
                        inferred_type = image_analysis.get("type_document") or infer_document_type_from_filename_or_content(filename, extracted_text)
                        new_doc = {
                            "nom_fichier": filename,
                            "type_document": inferred_type,
                            "description": image_analysis.get("description") or f"Document joint extrait automatiquement : {inferred_type}",
                            "contenu_brut": extracted_text,
                            "chemin_fichier": extracted_paths.get(filename, "")
                        }
                        if image_analysis.get("informations_extraites"):
                            new_doc["informations_extraites"] = image_analysis["informations_extraites"]
                        documents_joints.append(new_doc)
                        logger.info(f" Document joint ajouté automatiquement pour {filename} : {inferred_type}")

                # Enrichir les documents_joints déjà existants avec contenu et type si nécessaire
                for doc in documents_joints:
                    if not isinstance(doc, dict):
                        continue
                    filename = doc.get("nom_fichier") or doc.get("filename", "")
                    if not filename:
                        continue
                    if filename in extracted_files:
                        doc["contenu_brut"] = extracted_files[filename]
                    if not doc.get("chemin_fichier"):
                        doc["chemin_fichier"] = extracted_paths.get(filename, "")
                    current_type = (doc.get("type_document") or "").strip()
                    image_analysis = extracted_metadata.get(filename, {})
                    if not current_type or current_type.lower() == "autre":
                        content_sample = (doc.get("contenu_brut") or "")
                        doc["type_document"] = image_analysis.get("type_document") or infer_document_type_from_filename_or_content(filename, content_sample)
                        doc["description"] = doc.get("description") or image_analysis.get("description") or f"Document analysé : {doc['type_document']}"
                        if image_analysis.get("informations_extraites"):
                            doc["informations_extraites"] = image_analysis["informations_extraites"]
                        logger.info(f" Type de document inféré pour {filename} : {doc['type_document']}")

                # Vérification des documents manquants selon le type d'avenant détecté
                documents_joints = analysis_dict.get("documents_joints", [])
                if not isinstance(documents_joints, list):
                    documents_joints = []

                logger.info(f" Documents joints détectés : {documents_joints}")
                logger.info(f" Type d'avenant : {analysis_dict.get('type_avenant')}")

                calculated_missing = infer_missing_documents(analysis_dict.get("type_avenant"), documents_joints, rules_engine)
                logger.info(f" Documents manquants calculés : {calculated_missing}")
                
                # RÉCUPÉRATION DE L'IDENTITÉ DU CONTRAT (pour aller chercher les vraies données en base)
                donnees_extraites = analysis_dict.get("donnees", {})
                if not isinstance(donnees_extraites, dict):
                    donnees_extraites = {}
                numero_contrat = donnees_extraites.get("numero_contrat")
                client_email = extract_email_address(email_data.get("sender", ""))
                avenant_type = analysis_dict.get("type_avenant")

                # RECHERCHE EXPLICITE DU CONTRAT EN BASE (par numéro de contrat, puis par e-mail en secours)
                # On la fait ici (une seule fois) pour pouvoir : 1) l'afficher/la comparer aux données du LLM,
                # 2) la réutiliser pour la validation des règles métier, 3) l'utiliser pour l'historique.
                contract_data = {}
                if avenant_type:
                    contract_data = rules_engine.get_contract_info(contract_id=numero_contrat, email=client_email) or {}
                    contract_data = sanitize_contract_data(contract_data)
                    log_contract_cross_check(contract_data, donnees_extraites, client_email)

                # VALIDATION AVEC LE MOTEUR DE RÈGLES
                # On normalise les libellés de type_document (ex: "Carte nationale d'identité" -> "Carte d'identité")
                # avant validation, pour que la comparaison du moteur de règles corresponde aux libellés canoniques
                # utilisés dans business_rules.json.
                documents_pour_validation = []
                for doc in documents_joints:
                    if isinstance(doc, dict):
                        doc_normalise = dict(doc)
                        doc_normalise["type_document"] = normalize_document_type_label(doc.get("type_document", ""))
                        documents_pour_validation.append(doc_normalise)

                is_valid = True
                validation_errors = []
                if avenant_type:
                    # contract_data est transmis directement : le moteur de règles ne refait PAS de requête DB,
                    # il applique les checks métier (IBAN valide, contrat actif, âge minimum...) sur CES données réelles,
                    # combinées aux documents_joints extraits par le LLM.
                    is_valid, validation_errors = rules_engine.validate_avenant(
                        avenant_type,
                        documents_pour_validation,
                        contract_data=contract_data
                    )
                    
                    if validation_errors:
                        logger.warning(f"Validation échouée pour {avenant_type}: {validation_errors}")
                        for error in validation_errors:
                            logger.warning(f"  - {error}")
                    else:
                        logger.info(f"Validation réussie pour {avenant_type}")
                    
                    # Enregistrer les résultats de validation
                    rules_engine.log_validation_result(msg_id, "avenant", is_valid, validation_errors)
                
                if calculated_missing:
                    existing_missing = analysis_dict.get("pieces_manquantes", [])
                    if not isinstance(existing_missing, list):
                        existing_missing = []
                    analysis_dict["pieces_manquantes"] = list(dict.fromkeys(existing_missing + calculated_missing))
                    logger.info(f" Pièces manquantes finales : {analysis_dict['pieces_manquantes']}")

                # RAPPORT DE VALIDATION (règles métier + documents manquants) inclus dans le JSON final
                pieces_manquantes_finales = analysis_dict.get("pieces_manquantes", [])
                if not isinstance(pieces_manquantes_finales, list):
                    pieces_manquantes_finales = []

                dossier_conforme = is_valid and not pieces_manquantes_finales

                raisons_non_conformite = list(validation_errors) if validation_errors else []
                if pieces_manquantes_finales:
                    raisons_non_conformite += [f"Document manquant : {doc}" for doc in pieces_manquantes_finales]

                analysis_dict["validation_rapport"] = {
                    "conforme": dossier_conforme,
                    "erreurs_regles_metier": validation_errors,
                    "documents_manquants": pieces_manquantes_finales,
                    "raison_non_conformite": None if dossier_conforme else " | ".join(raisons_non_conformite),
                    "contrat_trouve_en_base": bool(contract_data),
                    "contrat_en_base": contract_data if contract_data else None
                }
                logger.info(f" Rapport de validation : {analysis_dict['validation_rapport']}")
                
                #  4. FILTRE STRICT : Est-ce un avenant d'assurance ?
                is_avenant = is_avenant_mail(analysis_dict)
                analysis_dict["is_avenant"] = is_avenant
                
                if is_avenant:
                    logger.info(f"AVENANT DÉTECTÉ. Lancement de la procédure de sauvegarde JSON...")
                    
                    # Consolidation de la donnée finale
                    final_output = {
                        "meta": {
                            "message_id": msg_id,
                            "subject": email_data["subject"],
                            "sender": email_data["sender"],
                            "date": email_data["date"],
                            "attachments_recues": [at["filename"] for at in email_data["attachments"]]
                        },
                        "intelligence_report": analysis_dict
                    }
                    
                    # A. Sauvegarde de l'e-mail brut (.eml)
                    FileManager.save_raw_email(msg_id, raw_bytes)
                    
                    # B. Sauvegarde locale du rapport JSON (uniquement pour les avenants !)
                    saved_path = FileManager.save_json_result(msg_id, final_output)
                    logger.info(f" Fichier JSON créé dans : {saved_path}")
                    
                    # C. Stockage final dans la base de données MySQL
                    db_success = DatabaseManager.save_analysis_to_db(final_output)
                    if db_success:
                        logger.info(f" Données enregistrées avec succès dans MySQL.")
                    else:
                        logger.error(f" Échec de l'enregistrement en base MySQL (voir l'erreur ci-dessus). Le JSON local reste disponible dans : {saved_path}")

                    # C-bis. Enregistrement de l'avenant dans l'historique (table avenant_history)
                    # ET application automatique de l'impact (mise à jour du contrat) si le dossier est CONFORME.
                    # avenant_history.contract_id référence contracts.id (clé numérique interne),
                    # PAS le contract_number texte -> on utilise l'id récupéré via contract_data.
                    statut_avenant = "validé" if dossier_conforme else "rejeté"
                    if contract_data.get("id"):
                        new_data = build_contract_update_payload(
                            avenant_type, donnees_extraites, documents_pour_validation, contract_data
                        ) if dossier_conforme else {}
                        if dossier_conforme and new_data:
                            logger.info(f" Application automatique de l'impact sur le contrat {contract_data['id']} : {new_data}")
                        elif dossier_conforme and not new_data:
                            logger.info(" Dossier conforme mais aucune donnée exploitable extraite pour mettre à jour le contrat automatiquement.")

                        applied = rules_engine.apply_avenant(
                            contract_id=contract_data["id"],
                            avenant_type=avenant_type,
                            new_data=new_data,
                            validation_errors=raisons_non_conformite if raisons_non_conformite else [],
                            message_id=msg_id
                        )
                        if applied:
                            logger.info(f" Avenant appliqué et historisé avec succès (contrat id={contract_data['id']}, statut={statut_avenant}).")
                        elif dossier_conforme:
                            logger.error(" Échec lors de l'application/l'historisation de l'avenant (voir l'erreur ci-dessus).")
                        else:
                            logger.info(f" Avenant rejeté historisé (contrat id={contract_data['id']}) - aucune modification appliquée au contrat.")
                    else:
                        logger.warning(" Aucun contrat trouvé en base -> avenant_history NON alimenté et aucune modification appliquée pour ce mail.")

                    # D. Envoi automatique d'un e-mail de notification au client
                    # (client_email a déjà été extrait plus haut, avant la validation)
                    email_envoi_info = {"envoye": False, "destinataire": client_email, "sujet": None, "corps": None}
                    if client_email:
                        try:
                            mailer = MailSender()
                            mailer.connect()

                            if dossier_conforme:
                                mail_subject, mail_body = build_validated_email(avenant_type)
                            else:
                                mail_subject, mail_body = build_missing_info_email(
                                    avenant_type,
                                    pieces_manquantes_finales,
                                    validation_errors
                                )

                            envoye = mailer.send_email(client_email, mail_subject, mail_body)
                            mailer.disconnect()

                            email_envoi_info.update({
                                "envoye": bool(envoye),
                                "sujet": mail_subject,
                                "corps": mail_body,
                            })
                        except Exception as mail_err:
                            logger.error(f"Erreur lors de l'envoi de l'e-mail automatique au client : {mail_err}")
                    else:
                        logger.warning("Impossible d'extraire l'adresse e-mail du client, aucun e-mail automatique envoyé.")

                    # E. Génération du rapport PDF récapitulatif (après analyse + envoi du mail automatique)
                    try:
                        pdf_path = FileManager.get_pdf_report_path(msg_id)
                        report_generator = ReportGenerator()
                        report_generator.generate_pdf_report(
                            final_output,
                            pdf_path,
                            email_envoi=email_envoi_info
                        )
                        logger.info(f" Rapport PDF généré dans : {pdf_path}")
                    except Exception as pdf_err:
                        logger.error(f"Erreur lors de la génération du rapport PDF : {pdf_err}")

                else:
                    # ⏭ SI CE N'EST PAS UN AVENANT : Rien n'est écrit (Ni JSON, Ni MySQL)
                    # Utilise 'type_avenant' pour correspondre à ton SYSTEM_PROMPT
                    logger.info(f"⏭ Mail REJETÉ (Type : '{analysis_dict.get('type_avenant')}'). Aucune action de stockage effectuée.")
                
            except Exception as inner_e:
                logger.error(f"Erreur lors du traitement de l'e-mail {tmp_id} : {inner_e}")
                continue

    except Exception as e:
        logger.critical(f"Erreur fatale sur le pipeline global : {e}")
    finally:
        downloader.disconnect()
        # Afficher les statistiques de validation
        stats = rules_engine.get_validation_statistics()
        logger.info(f"=== STATISTIQUES DE VALIDATION ===")
        logger.info(f"Total validations: {stats.get('total', 0)}")
        logger.info(f"Réussies: {stats.get('valid', 0)}")
        logger.info(f"Échouées: {stats.get('invalid', 0)}")
        logger.info(f"Taux de réussite: {stats.get('success_rate', '0%')}")
        logger.info("Session de traitement terminée.")

if __name__ == "__main__":
    run_pipeline()