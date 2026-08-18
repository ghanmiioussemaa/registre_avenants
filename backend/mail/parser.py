import email
from email.header import decode_header
import os
from typing import Dict, Any, List
from config import ATTACHMENT_FOLDER
from storage.file_manager import FileManager  # Ligne qui posait problème

class MailParser:
    @staticmethod
    def decode_mime_header(header_value: str) -> str:
        """Décode les entêtes encodés (ex: UTF-8, ISO)."""
        if not header_value:
            return ""
        decoded, encoding = decode_header(header_value)[0]
        if isinstance(decoded, bytes):
            return decoded.decode(encoding or "utf-8", errors="ignore")
        return str(decoded)

    @staticmethod
    def parse_email_bytes(raw_content: bytes) -> Dict[str, Any]:
        """Analyse le contenu brut du mail et extrait la structure complète."""
        msg = email.message_from_bytes(raw_content)
        
        subject = MailParser.decode_mime_header(msg["Subject"])
        sender = MailParser.decode_mime_header(msg["From"])
        date_str = MailParser.decode_mime_header(msg["Date"])
        message_id = msg["Message-ID"] or f"no_id_{hash(raw_content)}"
        
        body_text = ""
        attachments_meta = []
        
        # Nettoyage de l'ID pour les dossiers
        safe_id = FileManager.sanitize_filename(message_id)
        mail_attachment_dir = os.path.join(ATTACHMENT_FOLDER, safe_id)

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                # Extraction du corps textuel
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    charset = part.get_content_charset() or "utf-8"
                    body_text += part.get_payload(decode=True).decode(charset, errors="ignore")
                
                # Gestion des pièces jointes
                elif "attachment" in content_disposition or part.get_filename():
                    filename = MailParser.decode_mime_header(part.get_filename())
                    if filename:
                        os.makedirs(mail_attachment_dir, exist_ok=True)
                        file_path = os.path.join(mail_attachment_dir, filename)
                        
                        payload = part.get_payload(decode=True)
                        with open(file_path, "wb") as f:
                            f.write(payload)
                            
                        attachments_meta.append({
                            "filename": filename,
                            "content_type": content_type,
                            "size": len(payload),
                            "local_path": file_path
                        })
        else:
            charset = msg.get_content_charset() or "utf-8"
            body_text = msg.get_payload(decode=True).decode(charset, errors="ignore")

        return {
            "message_id": message_id,
            "subject": subject,
            "sender": sender,
            "date": date_str,
            "body": body_text.strip(),
            "attachments": attachments_meta
        }