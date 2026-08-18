import mysql.connector
import json
import logging
from email.utils import parsedate_to_datetime
from datetime import datetime
from config import MYSQL_CONFIG

logger = logging.getLogger("MailAI")


def _parse_email_date(raw_date: str):
    """
    Convertit une date d'en-tête d'e-mail (format RFC 2822, ex: 'Thu, 23 Jul 2026 11:15:43 +0100')
    en objet datetime naïf compatible avec une colonne MySQL DATETIME.
    Sans cette conversion, MySQL rejette la chaîne brute avec l'erreur 1292 'Incorrect datetime value'.
    """
    if not raw_date:
        return None
    try:
        parsed = parsedate_to_datetime(raw_date)
        if parsed.tzinfo is not None:
            # MySQL DATETIME ne stocke pas le fuseau horaire : on convertit en heure locale naïve.
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
    except (TypeError, ValueError) as e:
        logger.warning(f"Impossible de parser la date d'e-mail '{raw_date}' : {e}")
        return None

class DatabaseManager:
    @staticmethod
    def get_connection():
        """Établit et retourne une connexion à la base de données MySQL."""
        try:
            connection = mysql.connector.connect(**MYSQL_CONFIG)
            return connection
        except mysql.connector.Error as err:
            logger.error(f"Échec de connexion à MySQL : {err}")
            raise err

    @staticmethod
    def save_analysis_to_db(final_output: dict) -> bool:
        """Insère ou met à jour le rapport d'analyse d'un avenant dans MySQL."""
        connection = None
        cursor = None
        try:
            # 1. Récupération de la connexion
            connection = DatabaseManager.get_connection()
            cursor = connection.cursor()

            # 2. Préparation des variables à plat depuis le dictionnaire
            meta = final_output.get("meta", {})
            message_id = meta.get("message_id")
            subject = meta.get("subject")
            sender = meta.get("sender")
            date_received = _parse_email_date(meta.get("date"))
            
            # Conversion du dictionnaire d'intelligence en texte JSON valide pour MySQL
            report_json = json.dumps(final_output.get("intelligence_report", {}), ensure_ascii=False)

            # 3. Requête SQL avec sécurité contre les injections et gestion des doublons
            query = """
                INSERT INTO analyzed_emails (message_id, subject, sender, date_received, intelligence_report)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    subject = VALUES(subject),
                    sender = VALUES(sender),
                    intelligence_report = VALUES(intelligence_report);
            """
            
            # 4. Exécution et validation
            cursor.execute(query, (message_id, subject, sender, date_received, report_json))
            connection.commit()
            
            logger.info(f" [MySQL] Succès du stockage pour le mail ID: {message_id}")
            return True

        except Exception as e:
            logger.error(f" [MySQL] Erreur lors de l'enregistrement de l'avenant : {e}")
            return False
            
        finally:
            # 5. Fermeture propre des ressources dans tous les cas
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()