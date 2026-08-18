import imaplib
import logging
from typing import List, Tuple
from config import IMAP_SERVER, IMAP_PORT, EMAIL_ADDRESS, EMAIL_PASSWORD, EMAIL_BATCH_SIZE

logger = logging.getLogger("MailAI")

# Sans timeout explicite, imaplib peut rester bloqué INDÉFINIMENT si le serveur est
# injoignable/lent (pare-feu, mauvais port, réseau...). C'est ce qui provoquait un
# agent "coincé" en statut "En cours..." sur le dashboard sans jamais se terminer.
IMAP_TIMEOUT_SECONDS = 30

class MailDownloader:
    def __init__(self):
        self.mail = None

    def connect(self):
        """Se connecte au serveur de messagerie."""
        try:
            self.mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, timeout=IMAP_TIMEOUT_SECONDS)
            self.mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            self.mail.select("INBOX")
            logger.info("Connexion IMAP réussie.")
        except Exception as e:
            logger.error(f"Erreur de connexion IMAP : {e}")
            raise e

    def fetch_unread_emails(self) -> List[Tuple[str, bytes]]:
        """Récupère la liste des e-mails non lus (limité aux EMAIL_BATCH_SIZE plus récents)."""
        emails_fetched = []
        if not self.mail:
            self.connect()

        try:
            # Recherche des messages non lus
            status, response = self.mail.search(None, "UNSEEN")
            if status != "OK":
                return emails_fetched

            email_ids = response[0].split()
            logger.info(f"{len(email_ids)} nouveaux messages trouvés au total.")

            # Limiter le traitement aux EMAIL_BATCH_SIZE derniers e-mails (les plus récents).
            # Réglable via EMAIL_BATCH_SIZE dans .env (1 par défaut : un seul mail
            # analysé par lancement, pour pouvoir vérifier chaque dossier avant le suivant).
            recent_email_ids = email_ids[-EMAIL_BATCH_SIZE:] if EMAIL_BATCH_SIZE > 0 else email_ids
            logger.info(f"Limitation du traitement aux {len(recent_email_ids)} e-mail(s) les plus récent(s).")

            for e_id in recent_email_ids:
                # Fetch du mail complet (RFC822)
                status, msg_data = self.mail.fetch(e_id, "(RFC822)")
                if status == "OK":
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            # Génération d'un ID temporaire basé sur l'UID IMAP
                            msg_id_tmp = f"imap_uid_{e_id.decode()}"
                            emails_fetched.append((msg_id_tmp, response_part[1]))
                            
                            # Optionnel : décommenter pour marquer comme lu automatiquement
                            # self.mail.store(e_id, '+FLAGS', '\\Seen')
                        
            return emails_fetched
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des mails : {e}")
            return []

    def disconnect(self):
        """Ferme proprement la connexion."""
        if self.mail:
            try:
                self.mail.close()
                self.mail.logout()
            except:
                pass