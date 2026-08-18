import os
import json
import logging
import shutil
from pypdf import PdfReader
import pytesseract
from PIL import Image
from llm.extractor import GroqExtractor

logger = logging.getLogger("MailAI")

class AttachmentProcessor:
    @staticmethod
    def save_attachment(attachment: dict) -> bool:
        """Enregistre physiquement la pièce jointe sur le disque dur."""
        try:
            local_path = attachment.get("local_path")
            content = attachment.get("content")
            
            if not local_path or not content:
                logger.warning(f"Données manquantes pour sauvegarder la pièce jointe : {attachment.get('filename')}")
                return False
                
            # Créer les dossiers parents s'ils n'existent pas (ex: data/attachments/)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Écriture du contenu binaire (bytes) sur le disque
            with open(local_path, "wb") as f:
                f.write(content)
                
            logger.info(f"Pièce jointe enregistrée avec succès : {local_path}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde physique de la pièce jointe : {e}")
            return False

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """Soutire tout le texte d'un document PDF informatique."""
        text = ""
        try:
            if not os.path.exists(file_path):
                logger.error(f"Le fichier à extraire n'existe pas sur le disque : {file_path}")
                return "[Fichier introuvable]"

            reader = PdfReader(file_path)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Impossible de lire le PDF {file_path} : {e}")
            return f"[Erreur de lecture du PDF : {e}]"

    @staticmethod
    def infer_document_type_from_text(text: str = "", filename: str = "") -> str:
        """Infère un type de document à partir du nom du fichier et du contenu brut."""
        combined = f"{filename or ''} {text or ''}".lower()
        if any(term in combined for term in ["carte nationale d'identité", "carte d'identité", "cin", "numéro d'identité", "date de naissance", "cni"]):
            return "Carte d'identité"
        if any(term in combined for term in ["rib", "iban", "bic", "swift", "banque"]):
            return "RIB/IBAN"
        if any(term in combined for term in ["facture", "edf", "quittance", "domicile", "adresse"]):
            return "Justificatif de domicile"
        if any(term in combined for term in ["permis", "conduire"]):
            return "Permis de conduire"
        if any(term in combined for term in ["contrat", "avenant"]):
            return "Contrat"
        if any(term in combined for term in ["grise", "immatriculation"]):
            return "Carte grise"
        if any(term in combined for term in ["attestation"]):
            return "Attestation"
        return "Autre"

    @staticmethod
    def normalize_image_analysis_payload(payload: dict, filename: str = "") -> dict:
        """Normalise une réponse d'analyse d'image en un dictionnaire exploitable."""
        if not isinstance(payload, dict):
            payload = {}

        payload = dict(payload)
        type_document = (
            payload.get("type_document")
            or payload.get("type")
            or payload.get("document_type")
            or ""
        )
        if not type_document or str(type_document).lower() == "autre":
            type_document = AttachmentProcessor.infer_document_type_from_text(
                payload.get("contenu_brut") or payload.get("texte_visible") or payload.get("texte") or payload.get("raw_text") or payload.get("analysis") or "",
                filename or payload.get("nom_fichier") or payload.get("filename") or ""
            )

        description = payload.get("description") or f"Document analysé : {type_document}"
        contenu_brut = (
            payload.get("contenu_brut")
            or payload.get("texte_visible")
            or payload.get("texte")
            or payload.get("raw_text")
            or payload.get("analysis")
            or ""
        )
        if isinstance(contenu_brut, list):
            contenu_brut = "\n".join(str(item) for item in contenu_brut)

        informations_extraites = payload.get("informations_extraites") or payload.get("info") or {}
        if not isinstance(informations_extraites, dict):
            informations_extraites = {}

        return {
            "nom_fichier": filename or payload.get("nom_fichier") or payload.get("filename") or "",
            "type_document": str(type_document),
            "description": str(description),
            "contenu_brut": str(contenu_brut),
            "informations_extraites": informations_extraites,
        }

    @staticmethod
    def analyze_image_attachment(file_path: str, filename: str = "") -> dict:
        """Analyse une image et renvoie un dictionnaire structuré avec type, description et informations extraites."""
        try:
            extractor = GroqExtractor()
            response = extractor.analyze_image_with_llm(file_path)
            if isinstance(response, dict):
                return AttachmentProcessor.normalize_image_analysis_payload(response, filename)
            if isinstance(response, str):
                try:
                    parsed = json.loads(response)
                except Exception:
                    parsed = {"contenu_brut": response}
                return AttachmentProcessor.normalize_image_analysis_payload(parsed, filename)
        except Exception as e:
            logger.warning(f"Analyse structurée de l'image impossible : {e}")

        return {
            "nom_fichier": filename,
            "type_document": AttachmentProcessor.infer_document_type_from_text("", filename),
            "description": f"Image non traitée : {filename}",
            "contenu_brut": "[Image non traitée]",
            "informations_extraites": {},
        }

    @staticmethod
    def extract_text_from_image(file_path: str) -> str:
        """Extrait le texte d'une image avec Tesseract OCR, avec fallback si le moteur n'est pas disponible."""
        try:
            if not os.path.exists(file_path):
                logger.error(f"Le fichier image n'existe pas sur le disque : {file_path}")
                return "[Fichier introuvable]"

            candidates = []
            env_path = os.getenv("TESSERACT_CMD")
            if env_path:
                candidates.append(env_path)
            candidates.append(shutil.which("tesseract"))
            candidates.extend([
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
            ])

            tesseract_cmd = next((path for path in candidates if path and os.path.exists(path)), None)
            if not tesseract_cmd:
                logger.warning("Tesseract non trouvé. Utilisation du LLM visuel Groq comme fallback.")
                image_analysis = AttachmentProcessor.analyze_image_attachment(file_path, os.path.basename(file_path))
                return image_analysis.get("contenu_brut") or "[Aucun texte détecté dans l'image]"

            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            logger.info(f"Extraction OCR de l'image : {file_path}")
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image, lang='fra+eng')
            return text.strip() if text else "[Aucun texte détecté dans l'image]"
        except Exception as e:
            logger.error(f"Erreur OCR sur {file_path} : {e}")
            return f"[OCR non disponible : {e}]"