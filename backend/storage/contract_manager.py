"""
Gestionnaire du contrat - Récupère et gère les données du contrat depuis la base de données.
"""

import logging
import mysql.connector
from config import MYSQL_CONFIG
from datetime import datetime

logger = logging.getLogger("MailAI")


class ContractManager:
    """Gère l'accès et la récupération des données de contrat."""
    
    @staticmethod
    def get_connection():
        """Établit une connexion à MySQL."""
        try:
            connection = mysql.connector.connect(**MYSQL_CONFIG)
            return connection
        except mysql.connector.Error as err:
            logger.error(f"Échec de connexion à MySQL: {err}")
            return None
    
    @staticmethod
    def get_contract_by_id(contract_id: str) -> dict:
        """
        Récupère les données complètes d'un contrat.
        
        Args:
            contract_id: L'ID du contrat
            
        Returns:
            Dictionnaire avec les données du contrat ou vide si non trouvé
        """
        connection = ContractManager.get_connection()
        if not connection:
            logger.warning(f"Impossible de récupérer le contrat {contract_id}: pas de connexion DB")
            return {}
        
        try:
            cursor = connection.cursor(dictionary=True)
            
            query = """
                SELECT 
                    id,
                    contract_number,
                    subscriber_name,
                    email,
                    phone,
                    address,
                    iban,
                    account_holder,
                    cin_number,
                    status,
                    is_active,
                    premium_amount,
                    premium_paid,
                    driver_license_valid,
                    age,
                    effective_date,
                    creation_date
                FROM contracts
                WHERE id = %s OR contract_number = %s
                LIMIT 1
            """
            
            cursor.execute(query, (contract_id, contract_id))
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                logger.info(f"Contrat trouvé: {contract_id}")
                return result
            else:
                logger.warning(f"Contrat non trouvé: {contract_id}")
                return {}
        
        except mysql.connector.Error as err:
            logger.error(f"Erreur lors de la récupération du contrat: {err}")
            return {}
        finally:
            connection.close()
    
    @staticmethod
    def get_contract_by_email(email: str) -> dict:
        """
        Récupère les données du contrat par email du souscripteur.
        
        Args:
            email: L'email du souscripteur
            
        Returns:
            Dictionnaire avec les données du contrat
        """
        connection = ContractManager.get_connection()
        if not connection:
            logger.warning(f"Impossible de récupérer le contrat pour {email}: pas de connexion DB")
            return {}
        
        try:
            cursor = connection.cursor(dictionary=True)
            
            query = """
                SELECT 
                    id,
                    contract_number,
                    subscriber_name,
                    email,
                    phone,
                    address,
                    iban,
                    account_holder,
                    cin_number,
                    status,
                    is_active,
                    premium_amount,
                    premium_paid,
                    driver_license_valid,
                    age,
                    effective_date,
                    creation_date
                FROM contracts
                WHERE email = %s
                ORDER BY creation_date DESC
                LIMIT 1
            """
            
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                logger.info(f"Contrat trouvé pour {email}")
                return result
            else:
                logger.warning(f"Aucun contrat trouvé pour {email}")
                return {}
        
        except mysql.connector.Error as err:
            logger.error(f"Erreur lors de la recherche du contrat: {err}")
            return {}
        finally:
            connection.close()
    
    @staticmethod
    def update_contract_after_avenant(contract_id: str, avenant_type: str, 
                                     new_data: dict) -> bool:
        """
        Met à jour le contrat après application d'un avenant.
        
        Args:
            contract_id: L'ID du contrat
            avenant_type: Type d'avenant appliqué
            new_data: Nouvelles données à appliquer
            
        Returns:
            True si succès, False sinon
        """
        connection = ContractManager.get_connection()
        if not connection:
            logger.error(f"Impossible de mettre à jour le contrat: pas de connexion DB")
            return False
        
        try:
            cursor = connection.cursor()
            
            # Construire dynamiquement la requête UPDATE
            update_fields = []
            update_values = []
            
            field_mapping = {
                "address": "address",
                "iban": "iban",
                "account_holder": "account_holder",
                "subscriber_name": "subscriber_name",
                "email": "email",
                "phone": "phone",
                "age": "age",
                "cin_number": "cin_number"
            }
            
            for key, db_field in field_mapping.items():
                if key in new_data:
                    update_fields.append(f"{db_field} = %s")
                    update_values.append(new_data[key])
            
            if not update_fields:
                logger.warning(f"Aucun champ à mettre à jour pour {contract_id}")
                return True
            
            update_values.append(datetime.now())
            update_values.append(contract_id)
            
            query = f"""
                UPDATE contracts
                SET {', '.join(update_fields)}, updated_at = %s
                WHERE id = %s
            """
            
            cursor.execute(query, update_values)
            connection.commit()
            
            logger.info(f"Contrat {contract_id} mis à jour après avenant '{avenant_type}'")
            cursor.close()
            return True
        
        except mysql.connector.Error as err:
            logger.error(f"Erreur lors de la mise à jour du contrat: {err}")
            connection.rollback()
            return False
        finally:
            connection.close()
    
    @staticmethod
    def log_avenant_history(contract_id: str, avenant_type: str, 
                           status: str, validation_errors: list = None,
                           message_id: str = None) -> bool:
        """
        Enregistre l'historique des avenants appliqués.
        
        Args:
            contract_id: L'ID du contrat
            avenant_type: Type d'avenant
            status: Statut (validé, rejeté, en attente)
            validation_errors: Liste des erreurs de validation
            message_id: Identifiant du mail analysé (analyzed_emails.message_id),
                permet de relier cette ligne d'historique à son rapport PDF/JSON.
            
        Returns:
            True si succès, False sinon
        """
        connection = ContractManager.get_connection()
        if not connection:
            logger.error(f"Impossible d'enregistrer l'historique: pas de connexion DB")
            return False
        
        try:
            cursor = connection.cursor()
            
            errors_json = None
            if validation_errors:
                import json
                errors_json = json.dumps(validation_errors, ensure_ascii=False)
            
            query = """
                INSERT INTO avenant_history 
                (contract_id, avenant_type, status, validation_errors, message_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(query, (
                contract_id,
                avenant_type,
                status,
                errors_json,
                message_id,
                datetime.now()
            ))
            connection.commit()
            
            logger.info(f"Historique enregistré: {contract_id} - {avenant_type} - {status}")
            cursor.close()
            return True
        
        except mysql.connector.Error as err:
            logger.error(f"Erreur lors de l'enregistrement de l'historique: {err}")
            return False
        finally:
            connection.close()
    
    @staticmethod
    def get_avenant_history(contract_id: str) -> list:
        """
        Récupère l'historique des avenants d'un contrat.
        
        Args:
            contract_id: L'ID du contrat
            
        Returns:
            Liste des avenants
        """
        connection = ContractManager.get_connection()
        if not connection:
            logger.warning(f"Impossible de récupérer l'historique: pas de connexion DB")
            return []
        
        try:
            cursor = connection.cursor(dictionary=True)
            
            query = """
                SELECT 
                    id,
                    avenant_type,
                    status,
                    validation_errors,
                    message_id,
                    created_at
                FROM avenant_history
                WHERE contract_id = %s
                ORDER BY created_at DESC
            """
            
            cursor.execute(query, (contract_id,))
            results = cursor.fetchall()
            cursor.close()
            
            logger.info(f"Historique récupéré pour {contract_id}: {len(results)} avenants")
            return results or []
        
        except mysql.connector.Error as err:
            logger.error(f"Erreur lors de la récupération de l'historique: {err}")
            return []
        finally:
            connection.close()

    @staticmethod
    def delete_avenant_history(history_id) -> bool:
        """
        Supprime une ligne précise de l'historique des avenants.

        Args:
            history_id: L'identifiant (avenant_history.id) de la ligne à supprimer

        Returns:
            True si une ligne a bien été supprimée, False sinon
        """
        connection = ContractManager.get_connection()
        if not connection:
            logger.error("Impossible de supprimer l'historique: pas de connexion DB")
            return False

        try:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM avenant_history WHERE id = %s", (history_id,))
            connection.commit()
            deleted = cursor.rowcount > 0
            cursor.close()
            if deleted:
                logger.info(f"Ligne d'historique supprimée: id={history_id}")
            else:
                logger.warning(f"Aucune ligne d'historique trouvée pour id={history_id}")
            return deleted

        except mysql.connector.Error as err:
            logger.error(f"Erreur lors de la suppression de l'historique: {err}")
            connection.rollback()
            return False
        finally:
            connection.close()
