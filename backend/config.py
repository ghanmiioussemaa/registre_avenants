import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("MailAI")


def _clean_env(value):
    """Nettoie une valeur d'environnement (espaces, guillemets accidentels)."""
    if value is None:
        return None
    cleaned = value.strip().strip('"').strip("'")
    return cleaned or None


# Variables d'authentification
EMAIL_ADDRESS = _clean_env(os.getenv("EMAIL_ADDRESS"))
EMAIL_PASSWORD = _clean_env(os.getenv("EMAIL_PASSWORD"))
IMAP_SERVER = _clean_env(os.getenv("IMAP_SERVER"))
IMAP_PORT = int(_clean_env(os.getenv("IMAP_PORT")) or 993)
GROQ_API_KEY = _clean_env(os.getenv("GROQ_API_KEY"))

if GROQ_API_KEY:
    logger.info(f"GROQ_API_KEY chargée depuis .env (se termine par ...{GROQ_API_KEY[-4:]})")
else:
    logger.warning(
        "GROQ_API_KEY absente ou vide après lecture du fichier .env. "
        "Vérifiez : 1) le fichier s'appelle bien '.env' (pas '.env.txt'), "
        "2) il est dans le même dossier que app.py, "
        "3) la ligne est 'GROQ_API_KEY=votre_clé' sans espace ni guillemet superflu."
    )

# Configuration SMTP (envoi des e-mails automatiques au client)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

# Configuration des dossiers
# IMPORTANT : ancrés sur le dossier de ce fichier (agent1/), PAS sur le répertoire
# courant (os.getcwd()). Sans ça, lancer "python app.py" depuis agent1/ et
# "python dashboard/dashboard_app.py" depuis un autre dossier créait deux jeux de
# dossiers data/ et logs/ différents : le dashboard lisait alors un journal vide
# et ne retrouvait pas les rapports, alors que MySQL (chemin absolu) restait correct.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DATA_DIR = os.path.join(BASE_DIR, "data")
EMAIL_FOLDER = os.path.join(BASE_DATA_DIR, "emails")
ATTACHMENT_FOLDER = os.path.join(BASE_DATA_DIR, "attachments")
JSON_FOLDER = os.path.join(BASE_DATA_DIR, "json")
PDF_FOLDER = os.path.join(BASE_DATA_DIR, "pdf_reports")
LOG_FOLDER = os.path.join(BASE_DIR, "logs")

# Initialisation des dossiers de l'application
for folder in [EMAIL_FOLDER, ATTACHMENT_FOLDER, JSON_FOLDER, PDF_FOLDER, LOG_FOLDER]:
    os.makedirs(folder, exist_ok=True)
# Nombre maximum de mails non lus traités à chaque lancement de l'agent.
# Réglable via .env (EMAIL_BATCH_SIZE=...) sans toucher au code. Par défaut : 1
# seul mail par lancement, pour pouvoir observer le détail de chaque analyse
# avant de passer au suivant plutôt que de traiter un lot de 10 d'un coup.
EMAIL_BATCH_SIZE = int(_clean_env(os.getenv("EMAIL_BATCH_SIZE")) or 1)

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "IIA1",         
    "password": "Oussema123", 
    "database": "mail_agent_db",
    "charset": "utf8mb4"
}