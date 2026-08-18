import os
import logging
import json
import base64
import re
from groq import Groq
from config import GROQ_API_KEY
from llm.prompt import SYSTEM_PROMPT 

logger = logging.getLogger("MailAI")


def _strip_thinking(text: str) -> str:
    """
    Retire tout bloc <think>...</think> que le modèle Qwen pourrait renvoyer malgré
    reasoning_effort='none' (garde-fou). Sans ce nettoyage, le raisonnement interne du
    modèle (plusieurs milliers de caractères) pollue le texte transmis à l'étape suivante
    et peut masquer les informations réellement utiles avant troncature.
    """
    if not text:
        return text
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Repli si la balise de fermeture est absente (réponse coupée en plein raisonnement)
    if "<think>" in cleaned.lower() and "</think>" not in cleaned.lower():
        cleaned = re.sub(r"<think>.*", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()

class GroqExtractor:
    def __init__(self):
        self.client = None
        # Qwen 3.6 27B (Groq) : modèle multimodal texte + vision, utilisé pour l'extraction structurée
        self.model_name = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")

        if GROQ_API_KEY:
            # Timeout explicite : sans lui, un appel API qui ne répond jamais peut bloquer
            # tout le pipeline indéfiniment (et donc figer le dashboard en "En cours...").
            self.client = Groq(api_key=GROQ_API_KEY, timeout=60.0)
        else:
            logger.error("Clé API GROQ_API_KEY manquante dans la configuration.")

    def _build_fallback_analysis(self, email_data: dict, attachments_text: str) -> str:
        """Retourne une analyse de secours robuste si Groq ne répond pas."""
        sujet = (email_data.get("subject") or "").lower()
        corps = (email_data.get("body") or "").lower()
        texte = f"{sujet} {corps} {attachments_text}".lower()

        is_avenant = any(k in texte for k in ["avenant", "changement", "adresse", "rib", "nom", "information", "coordonnées"])
        type_avenant = None

        if "adresse" in texte:
            type_avenant = "Changement adresse"
        elif "rib" in texte:
            type_avenant = "Changement RIB"
        elif "nom" in texte:
            type_avenant = "Changement nom"
        elif "information" in texte or "coordonnées" in texte:
            type_avenant = "Correction informations personnelles"

        documents_joints = []
        if attachments_text:
            documents_joints.append({
                "nom_fichier": "pièce_jointe",
                "type_document": "Carte d'identité" if "ident" in texte or "cin" in texte else "Autre",
                "description": "Pièce jointe analysée via fallback local",
                "contenu_brut": attachments_text,
                "informations_extraites": {"date_validite": None}
            })

        return json.dumps({
            "is_avenant": is_avenant,
            "type_avenant": type_avenant,
            "confidence": 0.6 if is_avenant else 0.0,
            "resume": "Analyse fallback générée automatiquement suite à une erreur Groq.",
            "documents_joints": documents_joints,
            "donnees": {
                "numero_contrat": None,
                "nom_client": None,
                "details_modification": {}
            },
            "pieces_manquantes": []
        })

    def analyze_image_with_llm(self, file_path: str) -> str:
        """Utilise un modèle visuel Groq pour lire une image quand l'OCR n'est pas disponible."""
        if not self.client:
            return "[LLM visuel indisponible : clé API Groq absente]"

        try:
            with open(file_path, "rb") as img_file:
                encoded = base64.b64encode(img_file.read()).decode("utf-8")

            ext = os.path.splitext(file_path)[1].lower()
            mime_type = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".bmp": "image/bmp",
                ".tiff": "image/tiff",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".heic": "image/heic"
            }.get(ext, "image/png")

            candidate_models = [
                "qwen/qwen3.6-27b"
            ]
            env_model = os.getenv("GROQ_IMAGE_MODEL")
            if env_model and env_model not in candidate_models:
                candidate_models.insert(0, env_model)

            last_error = None
            for model_name in candidate_models:
                try:
                    logger.info(f"Tentative d'analyse visuelle avec le modèle : {model_name}")
                    completion = self.client.chat.completions.create(
                        model=model_name,
                        timeout=20,
                        reasoning_effort="none",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Analyse cette image comme un document. Classe précisément le type de document (ex: Carte d'identité, RIB/IBAN, Justificatif de domicile, Permis de conduire, Contrat, Carte grise, Autre), puis extrais tout texte visible et les informations utiles. Si c'est une carte d'identité, un CIN ou un passeport, indique explicitement et séparément le NUMÉRO de la pièce (ex: 'Numéro CIN : ...') et le NOM COMPLET du titulaire tel qu'imprimé (ex: 'Nom complet : ...'), sans les inventer si illisibles. Réponds en texte brut, concis et structuré."
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{mime_type};base64,{encoded}"
                                        }
                                    }
                                ]
                            }
                        ],
                        temperature=0.1
                    )
                    content = completion.choices[0].message.content
                    return _strip_thinking(content)
                except Exception as e:
                    last_error = e
                    logger.warning(f"Modèle vision {model_name} indisponible : {e}")
                    continue

            logger.error(f"Échec de l'analyse visuelle Groq avec tous les modèles : {last_error}")
            return f"[LLM visuel indisponible : {last_error}]"
        except Exception as e:
            logger.error(f"Échec de l'analyse visuelle Groq : {e}")
            return f"[LLM visuel indisponible : {e}]"

    def analyze_email_context(self, email_data: dict, attachments_text: str) -> str:
        """
        Demande à l'IA d'analyser le mail en utilisant le SYSTEM_PROMPT importé.
        """
        if not self.client:
            logger.warning("Client Groq indisponible, utilisation du fallback local.")
            return self._build_fallback_analysis(email_data, attachments_text)

        # Préparation des données du mail pour l'injection
        corps_mail = email_data.get('body', '')
        sujet_mail = email_data.get('subject', '')
        expediteur = email_data.get('sender', '')

        # Limite le texte des pièces jointes pour éviter un prompt trop volumineux
        if len(attachments_text) > 3200:
            logger.warning("Texte des pièces jointes trop long, tronçonnage avant appel à l'IA.")
            attachments_text = attachments_text[:3200] + "\n[...TRONCATED]"

        # Construction du message utilisateur (le contexte à analyser)
        prompt_utilisateur = f"""
        Voici les informations à analyser :
        
        SUJET DU MAIL: {sujet_mail}
        EXPÉDITEUR: {expediteur}
        CORPS DU MAIL: {corps_mail}
        
        TEXTE OU CONTENU EXTRAIT DES PIÈCES JOINTES (PDF / IMAGE / AUTRE) :
        {attachments_text}
        
        Si une image est fournie, utilise le texte OCR ou le contenu visuel disponible. Si un fichier ne contient pas de texte exploitable, base-toi sur son nom de fichier et son type pour identifier le document.
        
        Applique strictement les consignes de qualification et retourne l'objet JSON demandé.
        """

        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                timeout=20,
                reasoning_effort="none",
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT  # Ton prompt exact
                    },
                    {
                        "role": "user",
                        "content": prompt_utilisateur
                    }
                ],
                temperature=0.1,
                response_format={"type": "json_object"}  # Force Groq à répondre en JSON valide
            )
            
            return _strip_thinking(completion.choices[0].message.content)

        except Exception as e:
            logger.error(f"Échec de l'appel Groq : {e}")
            return self._build_fallback_analysis(email_data, attachments_text)