"""
Script d'installation automatique de la base de données.
Exécutez: python setup_db_automatic.py
"""

import mysql.connector
from mysql.connector import Error
import logging
import sys

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("DBSetup")


def read_config():
    """Lit la configuration depuis config.py"""
    try:
        from config import MYSQL_CONFIG
        return MYSQL_CONFIG
    except ImportError:
        logger.error("config.py non trouvé")
        sys.exit(1)


def test_connection(config):
    """Teste la connexion à MySQL"""
    print("\n" + "="*60)
    print("1️⃣  TEST DE CONNEXION À MYSQL")
    print("="*60)
    
    try:
        connection = mysql.connector.connect(
            host=config['host'],
            user=config['user'],
            password=config['password']
        )
        logger.info("✅ Connexion réussie à MySQL")
        connection.close()
        return True
    except Error as err:
        logger.error(f"❌ Erreur de connexion: {err}")
        logger.error("Vérifiez: host, user, password")
        return False


def create_database(config):
    """Crée la base de données si elle n'existe pas"""
    print("\n" + "="*60)
    print("2️⃣  CRÉATION DE LA BASE DE DONNÉES")
    print("="*60)
    
    try:
        connection = mysql.connector.connect(
            host=config['host'],
            user=config['user'],
            password=config['password']
        )
        cursor = connection.cursor()
        
        db_name = config['database']
        
        # Créer la base
        create_db_query = f"""
        CREATE DATABASE IF NOT EXISTS {db_name}
        CHARACTER SET utf8mb4
        COLLATE utf8mb4_unicode_ci;
        """
        
        cursor.execute(create_db_query)
        logger.info(f"✅ Base de données '{db_name}' créée/existe")
        
        cursor.close()
        connection.close()
        return True
    except Error as err:
        logger.error(f"❌ Erreur: {err}")
        return False


def create_tables(config):
    """Crée les tables"""
    print("\n" + "="*60)
    print("3️⃣  CRÉATION DES TABLES")
    print("="*60)
    
    try:
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()
        
        # Table contracts
        logger.info("Création de la table 'contracts'...")
        create_contracts = """
        CREATE TABLE IF NOT EXISTS contracts (
            id INT PRIMARY KEY AUTO_INCREMENT,
            contract_number VARCHAR(50) UNIQUE NOT NULL,
            subscriber_name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE,
            phone VARCHAR(20),
            address TEXT,
            iban VARCHAR(34),
            account_holder VARCHAR(255),
            cin_number VARCHAR(30),
            status VARCHAR(50) DEFAULT 'actif',
            is_active BOOLEAN DEFAULT TRUE,
            premium_amount DECIMAL(10, 2),
            premium_paid BOOLEAN DEFAULT FALSE,
            driver_license_valid BOOLEAN DEFAULT NULL,
            age INT,
            effective_date DATE,
            creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_email (email),
            INDEX idx_contract_number (contract_number),
            INDEX idx_is_active (is_active),
            INDEX idx_cin_number (cin_number)
        )
        """
        cursor.execute(create_contracts)
        logger.info("✅ Table 'contracts' créée")

        # Migration douce : si la table existait déjà (installation précédente) sans cin_number, on l'ajoute.
        try:
            cursor.execute("SHOW COLUMNS FROM contracts LIKE 'cin_number'")
            if not cursor.fetchone():
                cursor.execute(
                    "ALTER TABLE contracts ADD COLUMN cin_number VARCHAR(30) AFTER account_holder, "
                    "ADD INDEX idx_cin_number (cin_number)"
                )
                logger.info("✅ Colonne 'cin_number' ajoutée à la table 'contracts' existante")
        except Error as migration_err:
            logger.warning(f"Impossible de vérifier/ajouter la colonne cin_number : {migration_err}")
        
        # Table avenant_history
        logger.info("Création de la table 'avenant_history'...")
        create_history = """
        CREATE TABLE IF NOT EXISTS avenant_history (
            id INT PRIMARY KEY AUTO_INCREMENT,
            contract_id INT NOT NULL,
            avenant_type VARCHAR(100) NOT NULL,
            status VARCHAR(50) NOT NULL COMMENT 'validé, rejeté, en attente',
            validation_errors JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (contract_id) REFERENCES contracts(id),
            INDEX idx_contract_id (contract_id),
            INDEX idx_status (status),
            INDEX idx_created_at (created_at)
        )
        """
        cursor.execute(create_history)
        logger.info("✅ Table 'avenant_history' créée")
        
        # Table analyzed_emails
        logger.info("Création de la table 'analyzed_emails'...")
        create_emails = """
        CREATE TABLE IF NOT EXISTS analyzed_emails (
            id INT PRIMARY KEY AUTO_INCREMENT,
            message_id VARCHAR(255) UNIQUE NOT NULL,
            subject VARCHAR(255),
            sender VARCHAR(255),
            date_received DATETIME,
            intelligence_report JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            INDEX idx_sender (sender),
            INDEX idx_date_received (date_received)
        )
        """
        cursor.execute(create_emails)
        logger.info("✅ Table 'analyzed_emails' créée")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("✅ Toutes les tables créées avec succès")
        return True
    except Error as err:
        logger.error(f"❌ Erreur: {err}")
        return False


def insert_test_data(config):
    """Insère des données de test"""
    print("\n" + "="*60)
    print("4️⃣  INSERTION DE DONNÉES DE TEST")
    print("="*60)
    
    try:
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()
        
        # Vérifier s'il y a déjà des données
        cursor.execute("SELECT COUNT(*) FROM contracts")
        count = cursor.fetchone()[0]
        
        if count > 0:
            logger.info(f"ℹ️  Il existe déjà {count} contrats en BD")
            cursor.close()
            connection.close()
            return True
        
        # Insérer les données de test
        logger.info("Insertion des données de test...")
        insert_query = """
        INSERT INTO contracts 
        (contract_number, subscriber_name, email, phone, address, iban, account_holder, cin_number,
         is_active, premium_amount, premium_paid, driver_license_valid, age, effective_date)
        VALUES
        ('CNT-2026-001', 'Jean Dupont', 'jean.dupont@example.com', '0612345678', 
         '123 rue de Paris', 'FR1420041010050500013M02606', 'Jean Dupont', 'AB123456',
         TRUE, 500.00, TRUE, TRUE, 35, '2025-01-01'),
        
        ('CNT-2026-002', 'Marie Martin', 'marie.martin@example.com', '0687654321', 
         '456 avenue des Champs', 'FR1420041010050500013M02607', 'Marie Martin', 'CD654321',
         TRUE, 600.00, FALSE, TRUE, 42, '2025-02-15'),
        
        ('CNT-2026-003', 'Pierre Bernard', 'pierre.bernard@example.com', '0698765432', 
         '789 boulevard Saint-Germain', 'FR1420041010050500013M02608', 'Pierre Bernard', NULL,
         TRUE, 450.00, TRUE, FALSE, 28, '2025-03-01')
        """
        
        cursor.execute(insert_query)
        connection.commit()
        
        logger.info(f"✅ {cursor.rowcount} contrats de test insérés")
        
        cursor.close()
        connection.close()
        return True
    except Error as err:
        logger.error(f"❌ Erreur: {err}")
        return False


def insert_test_history(config):
    """Insère un historique de test"""
    print("\n" + "="*60)
    print("5️⃣  INSERTION D'HISTORIQUE DE TEST")
    print("="*60)
    
    try:
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()
        
        # Vérifier s'il y a déjà des historiques
        cursor.execute("SELECT COUNT(*) FROM avenant_history")
        count = cursor.fetchone()[0]
        
        if count > 0:
            logger.info(f"ℹ️  Il existe déjà {count} avenants dans l'historique")
            cursor.close()
            connection.close()
            return True
        
        logger.info("Insertion de l'historique de test...")
        
        insert_query = """
        INSERT INTO avenant_history 
        (contract_id, avenant_type, status, validation_errors)
        VALUES
        (1, 'Changement adresse', 'validé', NULL),
        (1, 'Changement RIB', 'validé', NULL),
        (2, 'Changement nom', 'rejeté', '["Document manquant: Justificatif de changement de nom"]')
        """
        
        cursor.execute(insert_query)
        connection.commit()
        
        logger.info(f"✅ {cursor.rowcount} avenants de test insérés")
        
        cursor.close()
        connection.close()
        return True
    except Error as err:
        logger.error(f"❌ Erreur: {err}")
        return False


def verify_data(config):
    """Vérifie que tout est correctement setup"""
    print("\n" + "="*60)
    print("6️⃣  VÉRIFICATION DE LA CONFIGURATION")
    print("="*60)
    
    try:
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()
        
        # Vérifier les tables
        cursor.execute("""
        SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_SCHEMA = %s
        """, (config['database'],))
        
        tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"Tables trouvées: {', '.join(tables)}")
        
        if 'contracts' not in tables:
            logger.error("❌ Table 'contracts' manquante")
            return False
        
        if 'avenant_history' not in tables:
            logger.error("❌ Table 'avenant_history' manquante")
            return False
        
        # Compter les données
        cursor.execute("SELECT COUNT(*) FROM contracts")
        contracts_count = cursor.fetchone()[0]
        logger.info(f"✅ {contracts_count} contrats trouvés")
        
        cursor.execute("SELECT COUNT(*) FROM avenant_history")
        history_count = cursor.fetchone()[0]
        logger.info(f"✅ {history_count} avenants trouvés")
        
        cursor.close()
        connection.close()
        
        logger.info("✅ Configuration vérifiée avec succès")
        return True
    except Error as err:
        logger.error(f"❌ Erreur: {err}")
        return False


def test_python_connection(config):
    """Teste que Python peut se connecter"""
    print("\n" + "="*60)
    print("7️⃣  TEST DE CONNEXION DEPUIS PYTHON")
    print("="*60)
    
    try:
        from storage.contract_manager import ContractManager
        
        logger.info("Test de récupération d'un contrat...")
        contract = ContractManager.get_contract_by_id("1")
        
        if contract:
            logger.info(f"✅ Contrat trouvé: {contract.get('contract_number')}")
            return True
        else:
            logger.warning("⚠️  Aucun contrat avec ID=1")
            return True
    except ImportError as e:
        logger.error(f"❌ Impossible d'importer ContractManager: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return False


def run_setup():
    """Exécute la configuration complète"""
    print("\n" + "#"*60)
    print("# 🔧 INSTALLATION AUTOMATIQUE DE LA BASE DE DONNÉES")
    print("#"*60)
    
    config = read_config()
    logger.info(f"Configuration: host={config['host']}, user={config['user']}, db={config['database']}")
    
    steps = [
        ("Connexion à MySQL", test_connection),
        ("Création de la base", create_database),
        ("Création des tables", create_tables),
        ("Insertion de données", insert_test_data),
        ("Insertion d'historique", insert_test_history),
        ("Vérification", verify_data),
        ("Test Python", test_python_connection)
    ]
    
    results = []
    for step_name, step_func in steps:
        try:
            result = step_func(config)
            results.append((step_name, result))
        except Exception as e:
            logger.error(f"Erreur lors de: {step_name} - {e}")
            results.append((step_name, False))
    
    # Résumé
    print("\n" + "#"*60)
    print("# ✅ RÉSUMÉ")
    print("#"*60)
    
    for step_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {step_name}")
    
    all_ok = all(result for _, result in results)
    
    if all_ok:
        print("\n" + "🎉 "*15)
        print("INSTALLATION COMPLÈTE ET RÉUSSIE!")
        print("Vous pouvez maintenant utiliser:")
        print("  • python test_business_rules.py")
        print("  • python example_usage.py")
        print("  • python app.py")
        print("🎉 "*15)
    else:
        print("\n❌ Certaines étapes ont échoué. Vérifiez les messages d'erreur.")
        sys.exit(1)


if __name__ == "__main__":
    run_setup()
