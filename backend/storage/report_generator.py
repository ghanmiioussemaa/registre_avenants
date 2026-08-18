import os
import logging
from datetime import datetime
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

logger = logging.getLogger("MailAI")


class ReportGenerator:
    """Génère un rapport PDF récapitulatif après l'analyse d'un mail/avenant
    et l'envoi automatique de la réponse au client."""

    # Couleurs de la charte du rapport
    COLOR_PRIMARY = colors.HexColor("#1F3B57")
    COLOR_OK = colors.HexColor("#1E7B34")
    COLOR_KO = colors.HexColor("#B02A2A")
    COLOR_GREY = colors.HexColor("#F2F2F2")

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._register_custom_styles()

    def _register_custom_styles(self):
        self.styles.add(ParagraphStyle(
            name="ReportTitle",
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=self.COLOR_PRIMARY,
            spaceAfter=4,
        ))
        self.styles.add(ParagraphStyle(
            name="ReportSubtitle",
            fontName="Helvetica",
            fontSize=10,
            textColor=colors.grey,
            spaceAfter=14,
        ))
        self.styles.add(ParagraphStyle(
            name="SectionTitle",
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=self.COLOR_PRIMARY,
            spaceBefore=14,
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name="BodyText2",
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            alignment=TA_LEFT,
        ))
        self.styles.add(ParagraphStyle(
            name="StatusOK",
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=self.COLOR_OK,
        ))
        self.styles.add(ParagraphStyle(
            name="StatusKO",
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=self.COLOR_KO,
        ))

    @staticmethod
    def _safe(value, default="—"):
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        return str(value)

    @classmethod
    def _safe_xml(cls, value, default="—"):
        """
        Comme _safe(), mais échappe en plus les caractères spéciaux XML (&, <, >).
        À utiliser IMPÉRATIVEMENT pour tout texte dynamique (issu d'un mail, d'un
        document, ou d'un message de règle métier) inséré dans un Paragraph
        reportlab : Paragraph interprète le texte comme du mini-XML, donc un
        simple '<' ou '&' non échappé (ex: un message du type "'age' (15) <
        minimum (18)") faisait planter toute la génération du PDF avec une
        exception silencieusement avalée par l'appelant (aucun PDF créé, sans
        erreur visible côté utilisateur).
        """
        return _xml_escape(cls._safe(value, default))

    def _build_header(self, meta: dict, story: list):
        story.append(Paragraph("Rapport d'analyse d'avenant", self.styles["ReportTitle"]))
        story.append(Paragraph(
            f"Généré automatiquement le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
            self.styles["ReportSubtitle"]
        ))
        story.append(HRFlowable(width="100%", color=self.COLOR_PRIMARY, thickness=1.2))
        story.append(Spacer(1, 10))

        info_table_data = [
            ["Sujet du mail", self._safe(meta.get("subject"))],
            ["Expéditeur", self._safe(meta.get("sender"))],
            ["Date de réception", self._safe(meta.get("date"))],
            ["Identifiant du message", self._safe(meta.get("message_id"))],
            ["Pièces jointes reçues", ", ".join(meta.get("attachments_recues", []) or []) or "—"],
        ]
        table = Table(info_table_data, colWidths=[4.5 * cm, 11.5 * cm])
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("TEXTCOLOR", (0, 0), (0, -1), self.COLOR_PRIMARY),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#DDDDDD")),
        ]))
        story.append(table)
        story.append(Spacer(1, 8))

    def _build_analysis_section(self, report: dict, story: list):
        story.append(Paragraph("Synthèse de l'analyse", self.styles["SectionTitle"]))

        type_avenant = self._safe(report.get("type_avenant"))
        confidence = report.get("confidence")
        confidence_str = f"{round(float(confidence) * 100)}%" if isinstance(confidence, (int, float)) else "—"
        resume = self._safe(report.get("resume"))

        data = [
            ["Type d'avenant détecté", type_avenant],
            ["Confiance du modèle", confidence_str],
        ]
        table = Table(data, colWidths=[4.5 * cm, 11.5 * cm])
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"<b>Résumé :</b> {self._safe_xml(resume)}", self.styles["BodyText2"]))
        story.append(Spacer(1, 6))

    def _build_validation_section(self, validation_rapport: dict, story: list):
        story.append(Paragraph("Résultat de la validation métier", self.styles["SectionTitle"]))

        conforme = bool(validation_rapport.get("conforme"))
        status_style = "StatusOK" if conforme else "StatusKO"
        status_label = "✔ DOSSIER CONFORME" if conforme else "✘ DOSSIER NON CONFORME"
        story.append(Paragraph(status_label, self.styles[status_style]))
        story.append(Spacer(1, 6))

        contrat_trouve = validation_rapport.get("contrat_trouve_en_base")
        story.append(Paragraph(
            f"<b>Contrat retrouvé en base :</b> {'Oui' if contrat_trouve else 'Non'}",
            self.styles["BodyText2"]
        ))

        contrat_en_base = validation_rapport.get("contrat_en_base") or {}
        if contrat_en_base:
            rows = [["Champ", "Valeur"]]
            for key, value in contrat_en_base.items():
                rows.append([str(key), self._safe(value)])
            table = Table(rows, colWidths=[5 * cm, 11 * cm])
            table.setStyle(self._grid_table_style(header=True))
            story.append(Spacer(1, 6))
            story.append(table)

        erreurs = validation_rapport.get("erreurs_regles_metier") or []
        story.append(Spacer(1, 8))
        story.append(Paragraph("<b>Erreurs de règles métier :</b>", self.styles["BodyText2"]))
        if erreurs:
            for err in erreurs:
                story.append(Paragraph(f"• {self._safe_xml(err)}", self.styles["BodyText2"]))
        else:
            story.append(Paragraph("Aucune", self.styles["BodyText2"]))

        docs_manquants = validation_rapport.get("documents_manquants") or []
        story.append(Spacer(1, 6))
        story.append(Paragraph("<b>Documents manquants :</b>", self.styles["BodyText2"]))
        if docs_manquants:
            for doc in docs_manquants:
                story.append(Paragraph(f"• {self._safe_xml(doc)}", self.styles["BodyText2"]))
        else:
            story.append(Paragraph("Aucun", self.styles["BodyText2"]))

        if not conforme and validation_rapport.get("raison_non_conformite"):
            story.append(Spacer(1, 6))
            story.append(Paragraph(
                f"<b>Raison de non-conformité :</b> {self._safe_xml(validation_rapport.get('raison_non_conformite'))}",
                self.styles["BodyText2"]
            ))

    def _build_documents_section(self, documents_joints: list, story: list):
        story.append(Paragraph("Documents joints analysés", self.styles["SectionTitle"]))

        if not documents_joints:
            story.append(Paragraph("Aucun document joint n'a été détecté dans ce mail.", self.styles["BodyText2"]))
            return

        rows = [["Fichier", "Type détecté", "Description"]]
        for doc in documents_joints:
            if not isinstance(doc, dict):
                continue
            rows.append([
                self._safe(doc.get("nom_fichier") or doc.get("filename")),
                self._safe(doc.get("type_document")),
                self._safe(doc.get("description")),
            ])

        table = Table(rows, colWidths=[4.5 * cm, 4 * cm, 7.5 * cm], repeatRows=1)
        table.setStyle(self._grid_table_style(header=True))
        story.append(table)

    def _build_email_section(self, email_envoi: dict, story: list):
        story.append(Paragraph("E-mail automatique envoyé au client", self.styles["SectionTitle"]))

        if not email_envoi or not email_envoi.get("envoye"):
            story.append(Paragraph(
                "Aucun e-mail automatique n'a pu être envoyé pour ce dossier "
                "(adresse destinataire manquante ou erreur d'envoi).",
                self.styles["BodyText2"]
            ))
            return

        data = [
            ["Destinataire", self._safe(email_envoi.get("destinataire"))],
            ["Objet", self._safe(email_envoi.get("sujet"))],
        ]
        table = Table(data, colWidths=[4.5 * cm, 11.5 * cm])
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
        story.append(Spacer(1, 6))
        story.append(Paragraph("<b>Corps du message :</b>", self.styles["BodyText2"]))
        corps = self._safe(email_envoi.get("corps"))
        for line in corps.split("\n"):
            story.append(Paragraph(self._safe_xml(line) if line.strip() else "&nbsp;", self.styles["BodyText2"]))

    def _grid_table_style(self, header: bool = False) -> TableStyle:
        style = [
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DDDDDD")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]
        if header:
            style += [
                ("BACKGROUND", (0, 0), (-1, 0), self.COLOR_PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        return TableStyle(style)

    def generate_pdf_report(self, final_output: dict, output_path: str, email_envoi: dict = None) -> str:
        """
        Construit le rapport PDF final à partir de la structure produite par le pipeline
        (final_output = {"meta": {...}, "intelligence_report": {...}}) et, optionnellement,
        des informations sur l'e-mail automatique envoyé au client.

        Retourne le chemin du fichier PDF généré.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        meta = final_output.get("meta", {}) or {}
        report = final_output.get("intelligence_report", {}) or {}
        validation_rapport = report.get("validation_rapport", {}) or {}
        documents_joints = report.get("documents_joints", []) or []

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=1.8 * cm,
            bottomMargin=1.8 * cm,
            title="Rapport d'analyse d'avenant",
        )

        story = []
        try:
            self._build_header(meta, story)
            self._build_analysis_section(report, story)
            self._build_validation_section(validation_rapport, story)
            self._build_documents_section(documents_joints, story)
            self._build_email_section(email_envoi, story)

            doc.build(story)
            logger.info(f"Rapport PDF généré avec succès : {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Échec de la génération du rapport PDF : {e}")
            raise
