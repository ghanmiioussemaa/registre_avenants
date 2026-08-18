import os
import json
import re

class FileManager:
    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Nettoie une chaîne pour en faire un nom de fichier valide."""
        return re.sub(r'[\\/*?:"<>| ]', '_', name)

    @staticmethod
    def save_raw_email(message_id: str, content: bytes) -> str:
        """Sauvegarde le mail brut sous format .eml."""
        from config import EMAIL_FOLDER
        safe_id = FileManager.sanitize_filename(message_id)
        file_path = os.path.join(EMAIL_FOLDER, f"{safe_id}.eml")
        with open(file_path, "wb") as f:
            f.write(content)
        return file_path

    @staticmethod
    def save_json_result(message_id: str, data: dict) -> str:
        """Sauvegarde le JSON final généré après analyse."""
        from config import JSON_FOLDER
        safe_id = FileManager.sanitize_filename(message_id)
        file_path = os.path.join(JSON_FOLDER, f"{safe_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return file_path

    @staticmethod
    def get_pdf_report_path(message_id: str) -> str:
        """Retourne le chemin de destination du rapport PDF pour ce message."""
        from config import PDF_FOLDER
        safe_id = FileManager.sanitize_filename(message_id)
        return os.path.join(PDF_FOLDER, f"{safe_id}_rapport.pdf")