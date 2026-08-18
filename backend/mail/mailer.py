import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parseaddr
from config import EMAIL_ADDRESS, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT

logger = logging.getLogger("MailAI")


class MailSender:
    """Gère l'envoi des e-mails automatiques de notification au client (SMTP)."""

    def __init__(self):
        self.server = None

    def connect(self):
        """Ouvre la connexion SMTP (TLS)."""
        try:
            self.server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20)
            self.server.starttls()
            self.server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            logger.info("Connexion SMTP réussie.")
        except Exception as e:
            logger.error(f"Erreur de connexion SMTP : {e}")
            raise e

    def send_email(self, to_address: str, subject: str, body: str) -> bool:
        """Envoie un e-mail texte simple au destinataire donné."""
        if not to_address:
            logger.warning("Adresse destinataire manquante, e-mail non envoyé.")
            return False

        if not self.server:
            self.connect()

        try:
            msg = MIMEMultipart()
            msg["From"] = EMAIL_ADDRESS
            msg["To"] = to_address
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            self.server.sendmail(EMAIL_ADDRESS, [to_address], msg.as_string())
            logger.info(f"E-mail automatique envoyé à {to_address} : {subject}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de l'e-mail à {to_address} : {e}")
            return False

    def disconnect(self):
        """Ferme proprement la connexion SMTP."""
        if self.server:
            try:
                self.server.quit()
            except Exception:
                pass


def extract_email_address(sender_header: str) -> str:
    """Extrait uniquement l'adresse e-mail depuis un champ 'From' (ex: 'Nom <email@x.com>')."""
    _, address = parseaddr(sender_header or "")
    return address


def build_missing_info_email(avenant_type: str, missing_documents: list, business_errors: list) -> tuple:
    """Construit (sujet, corps) de l'e-mail signalant un dossier incomplet / non conforme."""
    subject = f"Votre demande de {avenant_type or 'modification de contrat'} - Éléments manquants"

    lines = [
        "Bonjour,",
        "",
        f"Nous avons bien reçu votre demande concernant : {avenant_type or 'votre contrat'}.",
        "Après vérification, votre dossier est actuellement incomplet et ne peut pas être traité automatiquement.",
        "",
    ]

    if missing_documents:
        lines.append("Documents manquants :")
        for doc in missing_documents:
            lines.append(f"  - {doc}")
        lines.append("")

    if business_errors:
        lines.append("Points à corriger :")
        for err in business_errors:
            lines.append(f"  - {err}")
        lines.append("")

    lines.extend([
        "Merci de bien vouloir nous transmettre les éléments manquants afin que nous puissions",
        "poursuivre le traitement de votre dossier dans les meilleurs délais.",
        "",
        "Cordialement,",
        "Le service Gestion des Contrats",
    ])

    return subject, "\n".join(lines)


def build_validated_email(avenant_type: str) -> tuple:
    """Construit (sujet, corps) de l'e-mail confirmant un dossier validé."""
    subject = f"Votre demande de {avenant_type or 'modification de contrat'} a été validée"

    lines = [
        "Bonjour,",
        "",
        f"Nous vous confirmons que votre demande concernant : {avenant_type or 'votre contrat'} a bien été reçue et validée.",
        "Tous les documents et informations requis ont été vérifiés avec succès.",
        "Votre demande est en cours de traitement et sera appliquée à votre contrat dans les meilleurs délais.",
        "",
        "Cordialement,",
        "Le service Gestion des Contrats",
    ]

    return subject, "\n".join(lines)
