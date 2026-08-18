-- Script de création des tables pour le système de gestion des avenants
-- Exécutez ce script dans MySQL pour initialiser la structure

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
);

-- MIGRATION : si la table `contracts` existe déjà sans la colonne cin_number
-- (installation précédente), exécutez cette ligne une seule fois :
-- ALTER TABLE contracts ADD COLUMN cin_number VARCHAR(30) AFTER account_holder, ADD INDEX idx_cin_number (cin_number);

CREATE TABLE IF NOT EXISTS avenant_history (
    id INT PRIMARY KEY AUTO_INCREMENT,
    contract_id INT NOT NULL,
    avenant_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL COMMENT 'validé, rejeté, en attente',
    validation_errors JSON,
    message_id VARCHAR(255) COMMENT 'Relie la ligne au message analysé (analyzed_emails.message_id), pour retrouver son rapport PDF/JSON',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (contract_id) REFERENCES contracts(id),
    INDEX idx_contract_id (contract_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);

-- MIGRATION : si la table `avenant_history` existe déjà sans la colonne message_id
-- (installation précédente), exécutez cette ligne une seule fois pour pouvoir
-- télécharger le PDF de chaque avenant depuis la fiche contrat :
-- ALTER TABLE avenant_history ADD COLUMN message_id VARCHAR(255) AFTER validation_errors;

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
);

-- Données de test (optionnel)
-- Vous pouvez utiliser ce script pour créer des données de test

INSERT INTO contracts 
(contract_number, subscriber_name, email, phone, address, iban, account_holder, cin_number, is_active, premium_amount, premium_paid, driver_license_valid, age, effective_date)
VALUES
('CNT-2026-001', 'Jean Dupont', 'jean.dupont@example.com', '0612345678', '123 rue de Paris', 'FR1420041010050500013M02606', 'Jean Dupont', 'AB123456', TRUE, 500.00, TRUE, TRUE, 35, '2025-01-01'),
('CNT-2026-002', 'Marie Martin', 'marie.martin@example.com', '0687654321', '456 avenue des Champs', 'FR1420041010050500013M02607', 'Marie Martin', 'CD654321', TRUE, 600.00, FALSE, TRUE, 42, '2025-02-15'),
('CNT-2026-003', 'Pierre Bernard', 'pierre.bernard@example.com', '0698765432', '789 boulevard Saint-Germain', 'FR1420041010050500013M02608', 'Pierre Bernard', NULL, TRUE, 450.00, TRUE, FALSE, 28, '2025-03-01')
ON DUPLICATE KEY UPDATE email = VALUES(email);

-- Exemple d'historique d'avenants
INSERT INTO avenant_history 
(contract_id, avenant_type, status, validation_errors)
VALUES
(1, 'Changement adresse', 'validé', NULL),
(1, 'Changement RIB', 'validé', NULL),
(2, 'Changement nom', 'rejeté', '["Document manquant: Justificatif de changement de nom"]')
ON DUPLICATE KEY UPDATE status = VALUES(status);
