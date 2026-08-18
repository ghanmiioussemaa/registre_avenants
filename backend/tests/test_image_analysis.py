import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mail.attachment import AttachmentProcessor


def test_normalize_image_analysis_payload_adds_structured_fields():
    payload = {
        "type_document": "Justificatif de domicile",
        "description": "Facture d'électricité",
        "texte_visible": "EDF\nFacture 123\nAdresse: 1 rue de Paris",
        "informations_extraites": {
            "adresse": "1 rue de Paris",
            "montant": "120€"
        }
    }

    result = AttachmentProcessor.normalize_image_analysis_payload(payload, "facture.png")

    assert result["type_document"] == "Justificatif de domicile"
    assert result["description"] == "Facture d'électricité"
    assert result["contenu_brut"] == "EDF\nFacture 123\nAdresse: 1 rue de Paris"
    assert result["informations_extraites"]["adresse"] == "1 rue de Paris"
    assert result["informations_extraites"]["montant"] == "120€"
