from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, Any

class GenericData(BaseModel):
    #  ANCIENNEMENT AvenantData : On autorise désormais l'IA à ajouter des clés dynamiques 
    # pour s'adapter aux PDF entrants (ex: salles, horaires, matières, etc.)
    model_config = ConfigDict(extra="allow") 
    
    # On garde tes champs d'assurance par défaut au cas où
    numero_contrat: Optional[str] = Field(None, description="Le numéro de contrat mentionné (si applicable).")
    nom_client: Optional[str] = Field(None, description="Nom et prénom de l'émetteur ou du demandeur.")
    
    # Ce dictionnaire récupérera automatiquement TOUT le reste (les colonnes du PDF, les listes, etc.)
    details_extraits: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Toutes les informations clés extraites du PDF ou du mail classées par clés/valeurs."
    )

class EmailAnalysisResult(BaseModel):
    
    model_config = ConfigDict(extra="allow")
    
    sujet_principal: str = Field(..., description="Le thème principal du mail ou du PDF (ex: 'Répartition Salles Examens', 'Demande Avenant Auto').")
    is_avenant: bool = Field(..., description="True si le mail concerne explicitement une demande d'avenant d'assurance.")
    type_document: Optional[str] = Field(
        None, 
        description="Type ou catégorie du document identifié (ex: 'Planning d'examens', 'Changement adresse', 'Newsletter', 'Autre')."
    )
    confidence: float = Field(..., description="Score de confiance de l'extraction entre 0.0 et 1.0.")
    resume: str = Field(..., description="Un résumé clair et complet des informations principales trouvées.")
    documents_joints: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Liste des pièces jointes identifiées. Chaque document contient: filename, type_document, description, et contenu_brut (texte extrait du PDF ou OCR)."
    )
    donnees: GenericData = Field(..., description="Bloc dynamique contenant toutes les entités extraites du texte ou du PDF.")
    pieces_manquantes: List[str] = Field(
        default_factory=list, 
        description="Liste des pièces justificatives ou informations absentes mais nécessaires selon le contexte."
    )