"""
Exemple d'utilisation complet du moteur de règles avec accès à la base de données.
Ce script montre comment :
1. Récupérer un contrat depuis la BD
2. Valider un avenant
3. Appliquer l'avenant et mettre à jour la BD
"""

import logging
from business_rules_engine import BusinessRulesEngine

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("Example")


def example_1_simple_validation():
    """
    EXEMPLE 1: Valider un avenant sans contrat en BD
    (Validation basique des documents uniquement)
    """
    print("\n" + "="*70)
    print("EXEMPLE 1: Validation simple - sans accès à la BD")
    print("="*70)
    
    engine = BusinessRulesEngine("business_rules.json")
    
    # Données fournies dans l'email
    documents = [
        {"type_document": "Carte d'identité", "name": "id.pdf"},
        {"type_document": "Justificatif de domicile", "name": "facture.pdf"}
    ]
    
    contract_data = {
        "is_active": True,
        "address": "123 rue de Paris",
        "effective_date": "2026-07-03"
    }
    
    avenant_type = "Changement adresse"
    
    print(f"\nType d'avenant: {avenant_type}")
    print(f"Documents fournis: {len(documents)}")
    print(f"Données du contrat (fournies manuellement): {contract_data}")
    
    is_valid, errors = engine.validate_avenant(avenant_type, documents, contract_data)
    
    print(f"\n✓ Résultat: {'VALIDE' if is_valid else 'INVALIDE'}")
    if errors:
        for error in errors:
            print(f"  {error}")
    else:
        print("  Aucune erreur")


def example_2_with_database():
    """
    EXEMPLE 2: Valider un avenant EN UTILISANT les données de la BD
    (Récupération automatique du contrat depuis MySQL)
    """
    print("\n" + "="*70)
    print("EXEMPLE 2: Validation avec accès à la base de données")
    print("="*70)
    
    engine = BusinessRulesEngine("business_rules.json")
    
    # Supposons que nous avons l'email du client
    email = "client@example.com"
    
    # 1. RÉCUPÉRER LE CONTRAT DEPUIS LA BD
    print(f"\n1️⃣  Récupération du contrat pour: {email}")
    contract_data = engine.get_contract_info(email=email)
    
    if not contract_data:
        print("   ⚠️  Contrat non trouvé en BD")
        print("   (Utilisez EXEMPLE 1 pour validation manuelle)")
        return
    
    print(f"   ✓ Contrat trouvé:")
    print(f"     - ID: {contract_data.get('id')}")
    print(f"     - Numéro: {contract_data.get('contract_number')}")
    print(f"     - Nom: {contract_data.get('subscriber_name')}")
    print(f"     - Actif: {contract_data.get('is_active')}")
    
    # 2. DOCUMENTS FOURNIS PAR L'EMAIL
    print(f"\n2️⃣  Documents fournis:")
    documents = [
        {"type_document": "Carte d'identité", "name": "id.pdf"},
        {"type_document": "Justificatif de domicile", "name": "facture.pdf"}
    ]
    for doc in documents:
        print(f"   - {doc['type_document']}")
    
    # 3. VALIDER L'AVENANT
    print(f"\n3️⃣  Validation de l'avenant")
    avenant_type = "Changement adresse"
    is_valid, errors = engine.validate_avenant(
        avenant_type, 
        documents, 
        contract_data  # Les données de la BD sont utilisées automatiquement
    )
    
    print(f"   Résultat: {'✓ VALIDE' if is_valid else '✗ INVALIDE'}")
    if errors:
        for error in errors:
            print(f"     {error}")
    
    # 4. APPLIQUER L'AVENANT
    if is_valid:
        print(f"\n4️⃣  Application de l'avenant à la BD")
        new_data = {
            "address": "456 avenue des Champs"
        }
        
        success = engine.apply_avenant(
            contract_id=contract_data.get('id'),
            avenant_type=avenant_type,
            new_data=new_data,
            validation_errors=[] if is_valid else errors
        )
        
        if success:
            print(f"   ✓ Avenant appliqué avec succès")
        else:
            print(f"   ✗ Erreur lors de l'application")
    
    # 5. AFFICHER L'HISTORIQUE
    print(f"\n5️⃣  Historique des avenants")
    history = engine.get_contract_avenant_history(contract_data.get('id'))
    
    if not history:
        print("   Aucun historique disponible (table vide)")
    else:
        for avenant in history:
            print(f"   - {avenant.get('avenant_type')}: {avenant.get('status')}")


def example_3_complete_flow():
    """
    EXEMPLE 3: Flux complet - du email à la mise à jour
    """
    print("\n" + "="*70)
    print("EXEMPLE 3: Flux complet d'un email d'avenant")
    print("="*70)
    
    engine = BusinessRulesEngine("business_rules.json")
    
    # Données extraites de l'email
    email_data = {
        "sender": "jean.dupont@email.com",
        "subject": "Demande de changement de RIB",
        "body": "Bonjour, je souhaite changer mon RIB..."
    }
    
    print(f"\n📧 EMAIL REÇU")
    print(f"   De: {email_data['sender']}")
    print(f"   Sujet: {email_data['subject']}")
    
    # Étape 1: Récupérer le contrat
    print(f"\n1️⃣  Recherche du contrat")
    contract = engine.get_contract_info(email=email_data['sender'])
    
    if not contract:
        print(f"   ✗ Aucun contrat trouvé pour {email_data['sender']}")
        print(f"   → Avenant REJETÉ")
        return
    
    print(f"   ✓ Contrat trouvé: {contract.get('contract_number')}")
    
    # Étape 2: Identifier le type d'avenant (simplification)
    avenant_type = "Changement RIB"
    
    # Étape 3: Valider les documents
    print(f"\n2️⃣  Validation des documents")
    documents = [
        {"type_document": "RIB/IBAN", "name": "rib.pdf", "quality_score": 90},
        {"type_document": "Mandat SEPA signé", "name": "mandat.pdf", "quality_score": 85}
    ]
    
    docs_valid, docs_errors = engine.validate_documents(documents)
    print(f"   Résultat: {'✓ OK' if docs_valid else '✗ ERREUR'}")
    if docs_errors:
        for error in docs_errors:
            print(f"     {error}")
    
    # Étape 4: Valider l'avenant complet
    print(f"\n3️⃣  Validation complète de l'avenant '{avenant_type}'")
    is_valid, errors = engine.validate_avenant(
        avenant_type,
        documents,
        contract
    )
    
    print(f"   Résultat: {'✓ VALIDE' if is_valid else '✗ INVALIDE'}")
    if errors:
        for error in errors:
            print(f"     {error}")
    
    # Étape 5: Appliquer ou rejeter
    print(f"\n4️⃣  Action finale")
    
    if is_valid:
        # Données du nouvel IBAN à appliquer
        new_data = {
            "iban": "FR1420041010050500013M02606",
            "account_holder": contract.get('subscriber_name')
        }
        
        success = engine.apply_avenant(
            contract.get('id'),
            avenant_type,
            new_data,
            validation_errors=[]
        )
        
        if success:
            print(f"   ✓ AVENANT APPLIQUÉ")
            print(f"     Le contrat a été mis à jour automatiquement")
        else:
            print(f"   ✗ ERREUR lors de l'application")
    else:
        # Avenant rejeté
        engine.apply_avenant(
            contract.get('id'),
            avenant_type,
            {},
            validation_errors=errors
        )
        
        print(f"   ✗ AVENANT REJETÉ")
        print(f"     Raisons:")
        for error in errors:
            print(f"       - {error}")


def example_4_statistics():
    """
    EXEMPLE 4: Afficher les statistiques et le résumé des règles
    """
    print("\n" + "="*70)
    print("EXEMPLE 4: Statistiques et résumé des règles")
    print("="*70)
    
    engine = BusinessRulesEngine("business_rules.json")
    
    # Résumé des règles
    print(f"\n📋 RÉSUMÉ DES RÈGLES DISPONIBLES")
    summary = engine.get_rules_summary()
    for category, count in summary.items():
        print(f"   {category}: {count} règles")
    
    # Détail des avenants
    print(f"\n📋 TYPES D'AVENANTS DISPONIBLES")
    avenants = engine.rules.get('avenants', {})
    for avenant_name in avenants.keys():
        requirements = engine.get_avenant_requirements(avenant_name)
        print(f"\n   {avenant_name}:")
        print(f"     Documents: {', '.join(requirements.get('documents', []))}")
        print(f"     Vérifications: {', '.join(requirements.get('checks', []))}")


def show_menu():
    """Affiche le menu et exécute l'exemple choisi."""
    print("\n" + "#"*70)
    print("# EXEMPLES D'UTILISATION DU MOTEUR DE RÈGLES MÉTIER")
    print("#"*70)
    print("\nChoisissez un exemple:")
    print("  1 - Validation simple (sans BD)")
    print("  2 - Validation avec accès à la BD")
    print("  3 - Flux complet email → validation → mise à jour BD")
    print("  4 - Afficher les statistiques et résumé")
    print("  0 - Quitter")
    
    choice = input("\nVotre choix (0-4): ").strip()
    
    if choice == "1":
        example_1_simple_validation()
    elif choice == "2":
        example_2_with_database()
    elif choice == "3":
        example_3_complete_flow()
    elif choice == "4":
        example_4_statistics()
    elif choice == "0":
        print("Au revoir!")
        return False
    else:
        print("Choix invalide")
    
    return True


if __name__ == "__main__":
    # Exécuter tous les exemples automatiquement
    example_1_simple_validation()
    example_4_statistics()
    
    print("\n" + "#"*70)
    print("# ℹ️  Pour tester avec la BD:")
    print("# - Assurez-vous que MySQL est disponible")
    print("# - Exécutez: python example_usage.py")
    print("# - Choisissez l'option 2 ou 3 du menu")
    print("#"*70)
