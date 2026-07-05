"""
Agent C — Automatic PDF generation (steps 1, 3, 4, 5, 6).

Zero LLM calls in this module: it only knows the SHAPE of `AlignmentEdge` and
`Node` (via `ReportData`, prepared by agents.Agent_C.nodes.prepare_report_data),
never how they were computed.

Recommended code order: document skeleton (1, on paper) -> render_pdf with mocked
data (3) -> prepare_report_data (2) -> image composite (4) -> score presentation
(5) -> gap robustness (6). Code rendering before real data prep: isolate and test
the risky brick (layout) before wiring the rest.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from agents.Agent_C.nodes import make_composite_image, prepare_report_data
from agents.Agent_C.prompts import (
    CONFIDENCE_SCORE_CAPTION,
    LEGAL_DISCLAIMER,
    MISSING_DATA_LABEL,
    SEVERITY_LABELS,
    STATUS_LABELS,
)
from agents.common.schemas import AlignmentEdge, Graph, LegalQualification, ReportData

_SEVERITY_COLORS = {
    "high": colors.HexColor("#c0392b"),
    "medium": colors.HexColor("#e67e22"),
    "low": colors.HexColor("#f1c40f"),
    "none": colors.HexColor("#95a5a6"),
    "—": colors.HexColor("#bdc3c7"),
}


def _styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], fontSize=26, spaceAfter=6),
        "h2": ParagraphStyle("ReportH2", parent=base["Heading2"], spaceBefore=18, spaceAfter=8),
        "h3": ParagraphStyle("ReportH3", parent=base["Heading3"], spaceBefore=12, spaceAfter=6),
        "body": ParagraphStyle("ReportBody", parent=base["BodyText"], fontSize=10, leading=14),
        "small": ParagraphStyle("ReportSmall", parent=base["BodyText"], fontSize=8, textColor=colors.grey),
        "score": ParagraphStyle("ReportScore", parent=base["Title"], fontSize=48, spaceAfter=0),
        "disclaimer": ParagraphStyle("ReportDisclaimer", parent=base["BodyText"], fontSize=8,
                                      textColor=colors.HexColor("#7f4b00"),
                                      backColor=colors.HexColor("#fff3cd")),
    }


# ---------------------------------------------------------------------------
# Step 1 — document skeleton, section by section
# ---------------------------------------------------------------------------

def _cover_page(report: ReportData, styles: Dict[str, ParagraphStyle]) -> list:
    elements = []
    elements.append(Spacer(1, 3 * cm))
    elements.append(Paragraph("Comparative condition report", styles["title"]))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(Paragraph(report.address or report.property_id, styles["body"]))
    elements.append(Paragraph(
        f"Entry: {report.entry_date or '—'}   |   Exit: {report.exit_date or '—'}",
        styles["body"],
    ))
    elements.append(Spacer(1, 2 * cm))

    # Step 5 — large figure + methodology sentence, no false precision.
    score_pct = round(report.confidence_score * 100)
    elements.append(Paragraph("Global confidence score", styles["h3"]))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph(f"{score_pct}%", styles["score"]))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph(report.confidence_score_method + " " + CONFIDENCE_SCORE_CAPTION, styles["small"]))
    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph(f"Estimated total cost of divergences: {report.total_cost_eur:.0f} €", styles["h3"]))
    elements.append(PageBreak())
    return elements


def _summary_table(report: ReportData, styles: Dict[str, ParagraphStyle]) -> list:
    elements = [Paragraph("Summary table", styles["h2"])]

    header = ["Room", "Checkpoint", "Status", "Severity", "Est. cost"]
    data = [header]
    for row in report.summary_rows:
        if not row.data_available:
            data.append([row.room, row.checkpoint_id, MISSING_DATA_LABEL, "—", "—"])
            continue
        data.append([
            row.room,
            row.checkpoint_id,
            STATUS_LABELS.get(row.status, row.status),
            SEVERITY_LABELS.get(row.severity, row.severity),
            f"{row.cost_eur:.0f} €" if row.cost_eur else "—",
        ])

    table = Table(data, colWidths=[3 * cm, 4 * cm, 4 * cm, 3 * cm, 3 * cm], repeatRows=1)
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f7")]),
    ]
    for i, row in enumerate(report.summary_rows, start=1):
        color = _SEVERITY_COLORS.get(row.severity, colors.white)
        style_commands.append(("BACKGROUND", (3, i), (3, i), color))
    table.setStyle(TableStyle(style_commands))
    elements.append(table)

    if report.unchanged_checkpoints:
        elements.append(Spacer(1, 0.4 * cm))
        elements.append(Paragraph(
            f"{len(report.unchanged_checkpoints)} unchanged checkpoint(s), not detailed: "
            + ", ".join(report.unchanged_checkpoints),
            styles["small"],
        ))
    elements.append(PageBreak())
    return elements


def _detailed_sections(report: ReportData, styles: Dict[str, ParagraphStyle]) -> list:
    elements = [Paragraph("Divergence details", styles["h2"])]

    for section in report.detailed_sections:
        elements.append(Paragraph(f"{section.room} — {section.checkpoint_id}", styles["h3"]))

        if not section.data_available:
            elements.append(Paragraph(MISSING_DATA_LABEL, styles["body"]))
            elements.append(Spacer(1, 0.6 * cm))
            continue

        image_path = section.composite_image_path
        if image_path and os.path.exists(image_path):
            elements.append(Image(image_path, width=16 * cm, height=16 * cm * 0.4))
        elif section.entry_image_path and section.exit_image_path:
            elements.append(Paragraph("(entry)  |  (exit) — composite not generated", styles["small"]))

        elements.append(Spacer(1, 0.2 * cm))
        elements.append(Paragraph(f"<b>Reasoning:</b> {section.reasoning}", styles["body"]))
        elements.append(Paragraph(f"<b>Estimated cost:</b> {section.cost_eur:.0f} €", styles["body"]))

        if section.legal:
            legal = section.legal
            elements.append(Paragraph(
                f"<b>Legal qualification:</b> {legal.legal_qualification} — "
                f"responsibility: {legal.responsibility}"
                + (f" — wear deduction: {legal.abattement_pct:.0f}%" if legal.abattement_pct else ""),
                styles["body"],
            ))
            elements.append(Paragraph(f"<i>{legal.reasoning}</i>", styles["small"]))
            elements.append(Paragraph(" · ".join(legal.legal_basis), styles["small"]))

        elements.append(Spacer(1, 0.6 * cm))

    elements.append(PageBreak())
    return elements


def _negotiation_summary(report: ReportData, styles: Dict[str, ParagraphStyle]) -> list:
    elements = [Paragraph("Negotiation points summary", styles["h2"])]
    elements.append(Paragraph(f"Total: {report.total_cost_eur:.0f} €", styles["h3"]))

    if not report.negotiation_points:
        elements.append(Paragraph("No negotiation points identified.", styles["body"]))
    else:
        for point in report.negotiation_points:
            elements.append(Paragraph(f"• {point}", styles["body"]))

    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph(LEGAL_DISCLAIMER, styles["disclaimer"]))
    elements.append(Paragraph(report.disclaimer, styles["small"]))
    return elements


def render_pdf(report_data: ReportData, output_path: str) -> str:
    """Pure rendering: walks `report_data`, computes nothing. Testable with mocked
    data without ever calling Module B."""
    styles = _styles()
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    )

    elements: list = []
    elements += _cover_page(report_data, styles)
    elements += _summary_table(report_data, styles)
    elements += _detailed_sections(report_data, styles)
    elements += _negotiation_summary(report_data, styles)

    doc.build(elements)
    return output_path


def build_report(
    entry_graph: Graph,
    exit_graph: Graph,
    edges: List[AlignmentEdge],
    confidence_score: float,
    output_path: str,
    legal_qualifications: Optional[Dict[str, LegalQualification]] = None,
    address: Optional[str] = None,
    entry_date: Optional[str] = None,
    exit_date: Optional[str] = None,
    composites_dir: Optional[str] = None,
) -> str:
    """Full pipeline: prepare_report_data -> composites (step 4) -> render_pdf."""
    report_data = prepare_report_data(
        entry_graph, exit_graph, edges, confidence_score,
        legal_qualifications=legal_qualifications,
        address=address, entry_date=entry_date, exit_date=exit_date,
    )

    if composites_dir:
        os.makedirs(composites_dir, exist_ok=True)
        for section in report_data.detailed_sections:
            if section.data_available and section.entry_image_path and section.exit_image_path:
                try:
                    section.composite_image_path = make_composite_image(
                        section.entry_image_path, section.exit_image_path,
                        os.path.join(composites_dir, f"{section.room}_{section.checkpoint_id}.jpg"),
                    )
                except (FileNotFoundError, OSError):
                    section.composite_image_path = None  # Step 6: render handles absence gracefully

    return render_pdf(report_data, output_path)


if __name__ == "__main__":
    # Step 3 — validate layout with 100% mocked data, zero dependency on Modules A and B.
    from agents.common.schemas import DetailedSection, SummaryRow

    mock_report = ReportData(
        property_id="appt-12",
        address="12 rue de la Paix, 75002 Paris",
        entry_date="2025-01-01",
        exit_date="2026-01-01",
        confidence_score=0.87,
        summary_rows=[
            SummaryRow(checkpoint_id="mur_nord", room="salon", status="damage", severity="high", cost_eur=45, responsibility="locataire"),
            SummaryRow(checkpoint_id="sol", room="chambre", status="normal_wear", severity="low", cost_eur=0),
            SummaryRow(checkpoint_id="prise_electrique", room="salon", status="—", severity="—", cost_eur=0, data_available=False),
        ],
        detailed_sections=[
            DetailedSection(checkpoint_id="mur_nord", room="salon", reasoning="Localized impact incompatible with normal aging.", cost_eur=45),
            DetailedSection(checkpoint_id="sol", room="chambre", reasoning="Diffuse wear consistent with occupancy duration.", cost_eur=0),
            DetailedSection(checkpoint_id="prise_electrique", room="salon", reasoning="", cost_eur=0, data_available=False),
        ],
        unchanged_checkpoints=["mur_sud", "fenetre"],
        total_cost_eur=45,
        negotiation_points=["salon / mur_nord: Localized impact incompatible with normal aging. (~45 €)"],
    )

    render_pdf(mock_report, "rapport_mock.pdf")
    print("Mock PDF generated: rapport_mock.pdf")
