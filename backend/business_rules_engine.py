"""
Moteur de gestion des règles métier (Business Rules Engine).
Permet de définir, valider et appliquer des règles métier au système.
"""

import json
import logging
import os
import re
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, date
from pathlib import Path

logger = logging.getLogger("MailAI")

# Dossier du projet (agent1/), utilisé pour résoudre business_rules.json en chemin absolu
# et éviter tout souci si le script est lancé depuis un autre répertoire.
_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Import conditionnel - essayer d'importer le ContractManager si disponible
try:
    from storage.contract_manager import ContractManager
    HAS_CONTRACT_MANAGER = True
except ImportError:
    HAS_CONTRACT_MANAGER = False
    logger.warning("ContractManager non disponible - fonctionnalités DB désactivées")


class BusinessRulesEngine:
    """Moteur pour valider et appliquer les règles métier du système."""
    
    def __init__(self, rules_file: str = "business_rules.json"):
        """Initialise le moteur avec les règles depuis un fichier JSON."""
        # Si un chemin relatif est fourni, on le résout par rapport au dossier du
        # projet (et non au répertoire courant du process qui a lancé le script).
        if not os.path.isabs(rules_file):
            rules_file = os.path.join(_PROJECT_DIR, rules_file)
        self.rules_file = rules_file
        self.rules = self._load_rules()
        self.validation_results = []
        
    def _load_rules(self) -> Dict[str, Any]:
        """Charge les règles depuis le fichier JSON."""
        try:
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                rules = json.load(f)
            logger.info(f"Règles métier chargées depuis {self.rules_file}")
            return rules
        except FileNotFoundError:
            logger.error(f"Fichier de règles {self.rules_file} non trouvé")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Erreur de lecture du fichier JSON {self.rules_file}")
            return {}
    
    def reload_rules(self) -> None:
        """Recharge les règles depuis le fichier."""
        self.rules = self._load_rules()
        logger.info("Règles métier rechargées")
    
    def validate_email(self, email_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Valide les données d'un email selon les règles de contrôle des emails.
        
        Args:
            email_data: Dictionnaire contenant les données de l'email
            
        Returns:
            Tuple (est_valide, liste_erreurs)
        """
        errors = []
        
        email_rules = self.rules.get("email_rules", {}).get("rules", [])
        
        for rule in email_rules:
            rule_name = rule.get("name")
            rule_type = rule.get("type")
            
            if rule_type == "required_field":
                field = rule.get("field")
                if not email_data.get(field):
                    errors.append(f"ERREUR: Champ requis manquant '{field}' - {rule.get('description')}")
            
            elif rule_type == "email_format":
                sender = email_data.get("sender", "")
                if "@" not in sender or "." not in sender.split("@")[-1]:
                    errors.append(f"ERREUR: Format d'email invalide - {rule.get('description')}")
            
            elif rule_type == "attachment_required":
                attachments = email_data.get("attachments", [])
                if rule.get("required") and not attachments:
                    errors.append(f"ERREUR: Pièces jointes requises - {rule.get('description')}")
            
            elif rule_type == "min_length":
                field = rule.get("field")
                min_len = rule.get("min_length", 0)
                value = email_data.get(field, "")
                if len(str(value)) < min_len:
                    errors.append(f"ERREUR: '{field}' doit avoir au moins {min_len} caractères")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def validate_documents(self, documents: List[Dict[str, Any]], context: str = "") -> Tuple[bool, List[str]]:
        """
        Valide les documents selon les règles de contrôle des documents.
        
        Args:
            documents: Liste des documents avec leurs métadonnées
            context: Contexte additionnel (ex: type d'avenant)
            
        Returns:
            Tuple (est_valide, liste_erreurs)
        """
        errors = []
        
        document_rules = self.rules.get("document_rules", {}).get("rules", [])
        
        for rule in document_rules:
            rule_name = rule.get("name")
            rule_type = rule.get("type")
            
            if rule_type == "required_documents":
                required_types = rule.get("required_types", [])
                document_types = [doc.get("type_document", "").lower() for doc in documents]
                
                for required in required_types:
                    if not any(required.lower() in doc_type for doc_type in document_types):
                        errors.append(f"ERREUR: Document manquant: {required}")
            
            elif rule_type == "file_size_limit":
                max_size_mb = rule.get("max_size_mb", 25)
                for doc in documents:
                    size_mb = doc.get("size_mb", 0)
                    if size_mb > max_size_mb:
                        errors.append(f"ERREUR: Document '{doc.get('name')}' dépasse la limite ({size_mb}MB > {max_size_mb}MB)")
            
            elif rule_type == "file_type_allowed":
                allowed_types = rule.get("allowed_types", [])
                for doc in documents:
                    ext = Path(doc.get("name", "")).suffix.lower()
                    if ext and ext not in allowed_types:
                        errors.append(f"ERREUR: Type de fichier non autorisé: {ext}")
            
            elif rule_type == "document_quality":
                for doc in documents:
                    quality_score = doc.get("quality_score", 100)
                    min_quality = rule.get("min_quality_score", 70)
                    if quality_score < min_quality:
                        errors.append(f"ATTENTION: Qualité document faible '{doc.get('name')}' ({quality_score}%)")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def validate_data_quality(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Valide la qualité des données extraites.
        
        Args:
            data: Dictionnaire avec les données à valider
            
        Returns:
            Tuple (est_valide, liste_erreurs)
        """
        errors = []
        warnings = []
        
        quality_rules = self.rules.get("data_quality_rules", {}).get("rules", [])
        
        for rule in quality_rules:
            rule_type = rule.get("type")
            
            if rule_type == "field_completeness":
                required_fields = rule.get("required_fields", [])
                missing_fields = [f for f in required_fields if not data.get(f)]
                if missing_fields:
                    errors.append(f"ERREUR: Champs manquants: {', '.join(missing_fields)}")
            
            elif rule_type == "field_format":
                field = rule.get("field")
                expected_format = rule.get("format")
                value = data.get(field, "")
                
                if field == "email" and value:
                    if "@" not in value or "." not in value.split("@")[-1]:
                        errors.append(f"ERREUR: Format email invalide pour '{field}'")
                
                elif field == "phone" and value:
                    digits_only = ''.join(c for c in value if c.isdigit())
                    if len(digits_only) < 10:
                        warnings.append(f"ATTENTION: Numéro de téléphone suspect pour '{field}'")
            
            elif rule_type == "value_range":
                field = rule.get("field")
                min_val = rule.get("min")
                max_val = rule.get("max")
                value = data.get(field)
                
                if value is not None:
                    try:
                        value_num = float(value)
                        if min_val is not None and value_num < min_val:
                            errors.append(f"ERREUR: '{field}' ({value_num}) < minimum ({min_val})")
                        if max_val is not None and value_num > max_val:
                            errors.append(f"ERREUR: '{field}' ({value_num}) > maximum ({max_val})")
                    except (ValueError, TypeError):
                        pass
        
        is_valid = len(errors) == 0
        all_issues = errors + warnings
        return is_valid, all_issues
    
    def validate_business_logic(self, data: Dict[str, Any], scenario: str = "") -> Tuple[bool, List[str]]:
        """
        Valide la logique métier spécifique.
        
        Args:
            data: Données à valider
            scenario: Scénario métier (ex: "souscription", "arbitrage", "rachat")
            
        Returns:
            Tuple (est_valide, liste_erreurs)
        """
        errors = []
        
        if scenario in self.rules:
            scenario_rules = self.rules[scenario].get("rules", [])
            
            for rule in scenario_rules:
                rule_name = rule.get("name")
                condition = rule.get("condition")
                
                logger.info(f"Vérification de la règle '{rule_name}': {rule.get('description')}")
                
                # Vous pouvez ajouter ici une logique personnalisée par règle
                # Pour maintenant, on enregistre simplement la vérification
                if not self._evaluate_condition(data, condition):
                    errors.append(f"ERREUR: Règle '{rule_name}' non respectée - {rule.get('description')}")
        
        return len(errors) == 0, errors
    
    def validate_avenant(self, avenant_type: str, documents: List[Dict[str, Any]], 
                        contract_data: Dict[str, Any] = None,
                        contract_id: str = None,
                        email: str = None) -> Tuple[bool, List[str]]:
        """
        Valide un avenant d'assurance avec sa structure complète.
        
        Args:
            avenant_type: Type d'avenant (ex: "Changement adresse")
            documents: Liste des documents fournis
            contract_data: Données du contrat (optionnel)
            contract_id: ID du contrat pour récupérer depuis la DB (optionnel)
            email: Email du souscripteur pour récupérer le contrat (optionnel)
            
        Returns:
            Tuple (est_valide, liste_erreurs)
        """
        errors = []
        warnings = []
        contract_data = contract_data or {}
        
        # Si pas de données de contrat mais ID ou email fourni, récupérer depuis la DB
        if not contract_data and HAS_CONTRACT_MANAGER:
            if contract_id:
                logger.info(f"Récupération du contrat depuis DB: {contract_id}")
                contract_data = ContractManager.get_contract_by_id(contract_id)
            elif email:
                logger.info(f"Récupération du contrat depuis DB pour: {email}")
                contract_data = ContractManager.get_contract_by_email(email)
            
            if not contract_data:
                logger.warning(f"Données de contrat non disponibles pour validation")
        
        avenants_rules = self.rules.get("avenants", {})
        
        if avenant_type not in avenants_rules:
            errors.append(f"ERREUR: Type d'avenant inconnu '{avenant_type}'")
            return False, errors
        
        avenant_config = avenants_rules[avenant_type]
        
        # 1. VÉRIFICATION DES DOCUMENTS
        required_docs = avenant_config.get("documents", [])
        provided_doc_types = [doc.get("type_document", "").lower() for doc in documents]
        
        for required_doc in required_docs:
            required_normalized = required_doc.lower()
            if not any(required_normalized in provided.lower() for provided in provided_doc_types):
                errors.append(f"ERREUR: Document manquant '{required_doc}' pour {avenant_type}")
                logger.warning(f" Document requis ABSENT : '{required_doc}'")
            else:
                logger.info(f" Document requis présent : '{required_doc}'")
        
        # 2. VÉRIFICATION DES CONTRÔLES MÉTIER (sur les données réelles du contrat en base)
        checks = avenant_config.get("checks", [])
        logger.info(f" Exécution de {len(checks)} contrôle(s) métier pour '{avenant_type}' : {checks}")
        for check in checks:
            check_result = self._verify_check(check, contract_data, documents)
            if not check_result["valid"]:
                errors.append(f"ERREUR: {check_result['reason']} (contrôle : {check})")
                logger.warning(f" Check métier ÉCHOUÉ : '{check}' -> {check_result['reason']}")
            elif check_result.get("warning"):
                warnings.append(f"ATTENTION: {check} - {check_result['reason']}")
                logger.warning(f" Check métier (avertissement) : '{check}' -> {check_result['reason']}")
            else:
                logger.info(f" Check métier OK : '{check}' -> {check_result['reason']}")
        
        # 3. ENREGISTREMENT DE L'IMPACT
        impacts = avenant_config.get("impact", [])
        logger.info(f"Impacts attendus pour {avenant_type}: {impacts}")
        
        is_valid = len(errors) == 0
        all_issues = errors + warnings
        return is_valid, all_issues
    
    def _find_document(self, documents: List[Dict[str, Any]], type_keywords: List[str]) -> Optional[Dict[str, Any]]:
        """Retrouve, parmi les documents_joints (issus du LLM/OCR), celui dont le type correspond à un des mots-clés."""
        for doc in documents or []:
            if not isinstance(doc, dict):
                continue
            type_doc = (doc.get("type_document") or "").lower()
            if any(kw in type_doc for kw in type_keywords):
                return doc
        return None

    def _parse_date_flexible(self, raw: str) -> Optional[date]:
        """Parse une date en plusieurs formats courants (FR en priorité)."""
        raw = (raw or "").strip()
        if not raw:
            return None
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        return None

    def _extract_expiry_date(self, doc: Optional[Dict[str, Any]]) -> Optional[date]:
        """
        Extrait la date de validité/expiration d'un document à partir des données
        réellement extraites par le LLM/OCR (informations_extraites ou contenu_brut),
        et non depuis une valeur figée en base.
        """
        if not doc:
            return None

        informations = doc.get("informations_extraites") or {}
        if isinstance(informations, dict):
            for key in ("date_validite", "date_de_validite", "date_expiration", "validite", "expiration"):
                if informations.get(key):
                    parsed = self._parse_date_flexible(str(informations[key]))
                    if parsed:
                        return parsed

        # Repli : recherche par expression régulière dans le texte brut extrait (OCR / analyse visuelle)
        contenu = doc.get("contenu_brut") or ""
        pattern = r"(?:date\s+de\s+validit[ée]|date\s+d['’]expiration|valable\s+jusqu['’]au|expire\s+le)\s*:?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})"
        match = re.search(pattern, contenu, re.IGNORECASE)
        if match:
            return self._parse_date_flexible(match.group(1))

        return None

    def _normalize_name(self, name: str) -> str:
        """Normalise un nom pour comparaison (casse, espaces, accents simples)."""
        if not name:
            return ""
        normalized = " ".join(str(name).strip().lower().split())
        return normalized

    def _extract_identity_fields(self, doc: Optional[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
        """
        Extrait le numéro de CIN et le nom complet à partir des données réellement extraites
        par le LLM/OCR pour un document de type 'Carte d'identité' (informations_extraites),
        avec repli par expression régulière sur le texte brut si nécessaire.
        """
        if not doc:
            return None, None

        informations = doc.get("informations_extraites") or {}
        cin_number = None
        nom_complet = None
        if isinstance(informations, dict):
            for key in ("numero_cin", "numero_cni", "numero_piece_identite", "numero_identite", "cin"):
                if informations.get(key):
                    cin_number = str(informations[key]).strip()
                    break
            for key in ("nom_complet", "nom", "nom_prenom"):
                if informations.get(key):
                    nom_complet = str(informations[key]).strip()
                    break

        contenu = doc.get("contenu_brut") or ""
        if not cin_number and contenu:
            pattern = r"(?:num[ée]ro\s*(?:cin|cni|d['’]identit[ée])?|cin)\s*:?\s*n?°?\s*([A-Za-z0-9]{5,15})"
            match = re.search(pattern, contenu, re.IGNORECASE)
            if match:
                cin_number = match.group(1).strip()

        return cin_number, nom_complet

    def _verify_identity_coherence(self, contract_data: Dict[str, Any],
                                   documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Vérifie la cohérence entre la pièce d'identité (CIN) fournie dans les documents joints
        et les informations du contrat en base (souscripteur, numéro de CIN déjà enregistré).
        C'est ce contrôle qui empêche qu'un avenant soit validé pour une personne dont l'identité
        ne correspond pas au titulaire réel du contrat.
        """
        doc = self._find_document(documents, ["carte d'identité", "carte nationale d'identité", "cin", "passeport"])
        if not doc:
            return {
                "valid": False,
                "reason": "Aucune pièce d'identité fournie : impossible de vérifier la cohérence avec le contrat"
            }

        cin_doc, nom_doc = self._extract_identity_fields(doc)
        cin_db = contract_data.get("cin_number")
        cin_db = str(cin_db).strip() if cin_db else None
        nom_db = contract_data.get("subscriber_name")

        # 1. Comparaison du nom sur la pièce vs souscripteur en base (si les deux sont lisibles)
        if nom_doc and nom_db and self._normalize_name(nom_doc) != self._normalize_name(nom_db):
            return {
                "valid": False,
                "reason": (
                    f"Le nom lu sur la pièce d'identité ('{nom_doc}') ne correspond pas "
                    f"au titulaire du contrat en base ('{nom_db}')"
                )
            }

        # 2. Comparaison du numéro de CIN avec celui déjà enregistré pour ce contrat
        if cin_db and cin_doc and cin_doc.upper() != cin_db.upper():
            return {
                "valid": False,
                "reason": (
                    f"Le numéro de la pièce d'identité fournie ('{cin_doc}') ne correspond pas "
                    f"au numéro de CIN enregistré pour ce contrat ('{cin_db}')"
                )
            }

        if not cin_doc:
            return {
                "valid": True,
                "warning": True,
                "reason": "Numéro de pièce d'identité illisible sur le document : cohérence non vérifiable automatiquement"
            }

        if not cin_db:
            return {
                "valid": True,
                "reason": (
                    f"Numéro de pièce d'identité lu avec succès ({cin_doc}) ; aucun numéro n'était "
                    f"encore enregistré pour ce contrat, il sera associé automatiquement"
                )
            }

        return {"valid": True, "reason": f"Identité cohérente avec le contrat (CIN {cin_doc})"}

    def _verify_check(self, check: str, contract_data: Dict[str, Any], 
                     documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Vérifie un contrôle métier spécifique."""
        check_lower = check.lower()
        
        # Contrôles génériques
        if "contrat actif" in check_lower:
            is_active = contract_data.get("is_active", False)
            return {
                "valid": is_active,
                "reason": "Contrat inactif" if not is_active else "Contrat actif"
            }
        
        elif "adresse valide" in check_lower:
            address = contract_data.get("address", "")
            is_valid = bool(address and len(address) > 5)
            return {
                "valid": is_valid,
                "reason": "Adresse invalide" if not is_valid else "Adresse valide"
            }
        
        elif "date d'effet" in check_lower:
            effective_date = contract_data.get("effective_date")
            is_valid = effective_date is not None
            return {
                "valid": is_valid,
                "reason": "Date d'effet manquante" if not is_valid else "Date d'effet présente"
            }
        
        elif "iban valide" in check_lower:
            iban = contract_data.get("iban", "")
            # Simple validation IBAN (à adapter selon vos besoins)
            is_valid = bool(iban and len(iban) >= 15)
            return {
                "valid": is_valid,
                "reason": "IBAN invalide" if not is_valid else "IBAN valide"
            }
        
        elif "titulaire du compte" in check_lower:
            account_holder = contract_data.get("account_holder", "")
            subscriber = contract_data.get("subscriber_name", "")
            is_valid = bool(account_holder and subscriber and account_holder.lower() == subscriber.lower())
            return {
                "valid": is_valid,
                "warning": not is_valid,
                "reason": "Titulaire ne correspond pas au souscripteur" if not is_valid else "Correspondance OK"
            }
        
        elif "permis valide" in check_lower or "permis non expiré" in check_lower:
            doc = self._find_document(documents, ["permis de conduire", "permis"])
            expiry = self._extract_expiry_date(doc)
            if expiry is not None:
                is_valid = expiry >= date.today()
                return {
                    "valid": is_valid,
                    "reason": f"Permis invalide : expiré depuis le {expiry.isoformat()}" if not is_valid else f"Permis valide jusqu'au {expiry.isoformat()} (vérifié sur le document envoyé)"
                }
            # Repli : si aucune date n'a pu être extraite du document, on retombe sur le statut connu du contrat,
            # en le signalant clairement comme non vérifié sur pièce.
            flag_valid = contract_data.get("driver_license_valid")
            if flag_valid is not None:
                return {
                    "valid": bool(flag_valid),
                    "warning": True,
                    "reason": f"Date de validité illisible sur le document -> statut de secours utilisé (dossier contrat: {'valide' if flag_valid else 'invalide'})"
                }
            return {"valid": False, "reason": "Impossible de vérifier la validité du permis : aucune date lisible sur le document et aucun statut en base"}

        elif "pièce d'identité" in check_lower and ("expir" in check_lower or "valide" in check_lower):
            doc = self._find_document(documents, ["carte d'identité", "carte nationale d'identité", "cin", "passeport"])
            expiry = self._extract_expiry_date(doc)
            if expiry is not None:
                is_valid = expiry >= date.today()
                return {
                    "valid": is_valid,
                    "reason": f"CIN invalide : expirée depuis le {expiry.isoformat()}" if not is_valid else f"CIN valide jusqu'au {expiry.isoformat()} (vérifié sur le document envoyé)"
                }
            return {
                "valid": False,
                "warning": True,
                "reason": "Impossible de vérifier la date de validité de la pièce d'identité (aucune date lisible sur le document envoyé)"
            }

        elif "correspondance avec le contrat" in check_lower or "vérification de l'identité" in check_lower or "verification de l'identite" in check_lower:
            return self._verify_identity_coherence(contract_data, documents)

        elif "âge minimum" in check_lower:
            age = contract_data.get("age")
            is_valid = age is not None and age >= 18
            return {
                "valid": is_valid,
                "reason": f"Âge insuffisant ({age})" if not is_valid else "Âge conforme"
            }
        
        elif "prime à jour" in check_lower:
            is_paid = contract_data.get("premium_paid", False)
            return {
                "valid": is_paid,
                "reason": "Prime impayée" if not is_paid else "Prime à jour"
            }
        
        # Par défaut, accepter le contrôle
        return {"valid": True, "reason": "Vérification personnalisée"}
    
    def get_avenant_requirements(self, avenant_type: str) -> Dict[str, Any]:
        """Retourne les exigences complètes pour un type d'avenant."""
        avenants = self.rules.get("avenants", {})
        return avenants.get(avenant_type, {})
    
    def _evaluate_condition(self, data: Dict[str, Any], condition: str) -> bool:
        """Évalue une condition spécifique. À adapter selon vos besoins."""
        # Placeholder pour logique personnalisée
        # Vous pouvez implémenter un vrai evaluateur d'expressions ici
        return True
    
    def get_rules_summary(self) -> Dict[str, int]:
        """Retourne un résumé du nombre de règles par catégorie."""
        summary = {}
        for category, content in self.rules.items():
            if isinstance(content, dict) and "rules" in content:
                summary[category] = len(content.get("rules", []))
        # Cas particulier : business_rules.json ne contient qu'une clé "avenants"
        # (pas de sous-clé "rules"), donc la boucle ci-dessus ne la voit jamais.
        # Sans ce bloc, le résumé restait toujours vide ({}) même quand le fichier
        # était bien chargé, ce qui donnait l'impression trompeuse d'un échec.
        avenants = self.rules.get("avenants")
        if isinstance(avenants, dict):
            summary["avenants"] = len(avenants)
        return summary
    
    def log_validation_result(self, entity_id: str, entity_type: str, 
                             is_valid: bool, errors: List[str]) -> None:
        """Enregistre le résultat d'une validation."""
        result = {
            "timestamp": datetime.now().isoformat(),
            "entity_id": entity_id,
            "entity_type": entity_type,
            "valid": is_valid,
            "errors": errors,
            "error_count": len(errors)
        }
        self.validation_results.append(result)
        
        if not is_valid:
            logger.warning(f"Validation échouée pour {entity_type} {entity_id}: {errors}")
        else:
            logger.info(f"Validation réussie pour {entity_type} {entity_id}")
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """Retourne des statistiques sur les validations effectuées."""
        if not self.validation_results:
            return {"total": 0, "valid": 0, "invalid": 0}
        
        total = len(self.validation_results)
        valid = sum(1 for r in self.validation_results if r["valid"])
        invalid = total - valid
        
        return {
            "total": total,
            "valid": valid,
            "invalid": invalid,
            "success_rate": f"{(valid/total*100):.1f}%" if total > 0 else "0%"
        }
    
    def apply_avenant(self, contract_id: str, avenant_type: str, 
                     new_data: Dict[str, Any], validation_errors: List[str] = None,
                     message_id: str = None) -> bool:
        """
        Applique un avenant au contrat et met à jour la base de données.
        
        Args:
            contract_id: ID du contrat
            avenant_type: Type d'avenant
            new_data: Nouvelles données à appliquer
            validation_errors: Erreurs de validation (le cas échéant)
            message_id: Identifiant du mail analysé, pour relier l'historique à son
                rapport PDF/JSON (permet le téléchargement depuis la fiche contrat).
            
        Returns:
            True si succès, False sinon
        """
        if not HAS_CONTRACT_MANAGER:
            logger.error("ContractManager non disponible - impossible d'appliquer l'avenant")
            return False
        
        validation_errors = validation_errors or []
        
        # Déterminer le statut
        status = "validé" if not validation_errors else "rejeté"
        
        # Enregistrer dans l'historique
        history_recorded = ContractManager.log_avenant_history(
            contract_id,
            avenant_type,
            status,
            validation_errors,
            message_id=message_id
        )
        
        if not history_recorded:
            logger.error(f"Impossible d'enregistrer l'historique de l'avenant")
            return False
        
        # Si validation réussie, mettre à jour le contrat
        if not validation_errors:
            contract_updated = ContractManager.update_contract_after_avenant(
                contract_id,
                avenant_type,
                new_data
            )
            
            if contract_updated:
                logger.info(f"Avenant '{avenant_type}' appliqué au contrat {contract_id}")
                return True
            else:
                logger.error(f"Erreur lors de la mise à jour du contrat {contract_id}")
                return False
        else:
            logger.warning(f"Avenant '{avenant_type}' rejeté pour {contract_id}")
            return False
    
    def get_contract_info(self, contract_id: str = None, email: str = None) -> Dict[str, Any]:
        """
        Récupère les informations du contrat depuis la BD.
        
        Args:
            contract_id: ID du contrat
            email: Email du souscripteur
            
        Returns:
            Dictionnaire avec les données du contrat
        """
        if not HAS_CONTRACT_MANAGER:
            logger.warning("ContractManager non disponible")
            return {}
        
        if contract_id:
            return ContractManager.get_contract_by_id(contract_id)
        elif email:
            return ContractManager.get_contract_by_email(email)
        else:
            return {}
    
    def get_contract_avenant_history(self, contract_id: str) -> List[Dict[str, Any]]:
        """
        Récupère l'historique des avenants d'un contrat.
        
        Args:
            contract_id: ID du contrat
            
        Returns:
            Liste des avenants historisés
        """
        if not HAS_CONTRACT_MANAGER:
            logger.warning("ContractManager non disponible")
            return []
        
        return ContractManager.get_avenant_history(contract_id)
