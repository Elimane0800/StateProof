"""
Agent C — Préparation des données (Étape 2) + composite d'images (Étape 4).

prepare_report_data sépare volontairement la préparation des données du
rendu : elle trie les edges par sévérité, calcule le total des coûts,
regroupe les checkpoints "inchangé", et gère les trous (Étape 6 — un
checkpoint dont l'image ou la classification manque devient
`data_available=False`, jamais une exception).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PIL import Image as PILImage, ImageDraw, ImageFont

from agents.common.schemas import (
    AlignmentEdge,
    DetailedSection,
    Graph,
    LegalQualification,
    ReportData,
    SummaryRow,
)

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "none": 3}


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def prepare_report_data(
    entry_graph: Graph,
    exit_graph: Graph,
    edges: List[AlignmentEdge],
    score: float,
    legal_qualifications: Optional[Dict[str, LegalQualification]] = None,
    address: Optional[str] = None,
    entry_date: Optional[str] = None,
    exit_date: Optional[str] = None,
) -> ReportData:
    legal_qualifications = legal_qualifications or {}
    edges_by_id = {e.node_id: e for e in edges}
    all_ids = sorted(entry_graph.checkpoint_node_ids() | exit_graph.checkpoint_node_ids())

    summary_rows: List[SummaryRow] = []
    detailed_sections: List[DetailedSection] = []
    unchanged: List[str] = []
    negotiation_points: List[str] = []
    total_cost = 0.0

    for node_id in all_ids:
        entry_node = entry_graph.get_node(node_id)
        exit_node = exit_graph.get_node(node_id)
        edge = edges_by_id.get(node_id)
        reference_node = entry_node or exit_node
        room = reference_node.room
        checkpoint_id = reference_node.checkpoint_id

        # Étape 6 — gérer les trous : image/classification manquante ou
        # échec Module A/B -> ligne "donnée non disponible", jamais un crash.
        data_available = (
            entry_node is not None
            and exit_node is not None
            and edge is not None
            and not entry_node.extraction_failed
            and not exit_node.extraction_failed
            and not edge.comparison_failed
        )

        if not data_available:
            summary_rows.append(
                SummaryRow(
                    checkpoint_id=checkpoint_id, room=room, status="—", severity="—",
                    cost_eur=0.0, data_available=False,
                )
            )
            detailed_sections.append(
                DetailedSection(
                    checkpoint_id=checkpoint_id, room=room,
                    entry_image_path=entry_node.image_path if entry_node else None,
                    exit_image_path=exit_node.image_path if exit_node else None,
                    reasoning="", cost_eur=0.0, data_available=False,
                )
            )
            continue

        status = _enum_value(edge.status)
        if status == "unchanged":
            # Regroupés, pas détaillés un par un.
            unchanged.append(checkpoint_id)
            continue

        legal = legal_qualifications.get(node_id)
        severity = _enum_value(edge.severity)

        summary_rows.append(
            SummaryRow(
                checkpoint_id=checkpoint_id, room=room, status=status, severity=severity,
                cost_eur=edge.estimated_cost_eur,
                responsibility=legal.responsibility if legal else None,
            )
        )
        detailed_sections.append(
            DetailedSection(
                checkpoint_id=checkpoint_id, room=room,
                entry_image_path=entry_node.image_path, exit_image_path=exit_node.image_path,
                reasoning=edge.reasoning, legal=legal, cost_eur=edge.estimated_cost_eur,
            )
        )
        total_cost += edge.estimated_cost_eur

        if status == "damage":
            negotiation_points.append(
                f"{room} / {checkpoint_id} : {edge.reasoning} (~{edge.estimated_cost_eur:.0f} €)"
            )

    summary_rows.sort(key=lambda r: (_SEVERITY_ORDER.get(r.severity, 9), -r.cost_eur))
    detailed_sections.sort(key=lambda s: -s.cost_eur)

    return ReportData(
        property_id=entry_graph.property_id,
        address=address,
        entry_date=entry_date,
        exit_date=exit_date,
        confidence_score=score,
        summary_rows=summary_rows,
        detailed_sections=detailed_sections,
        unchanged_checkpoints=unchanged,
        total_cost_eur=round(total_cost, 2),
        negotiation_points=negotiation_points,
    )


def make_composite_image(
    entry_image_path: str,
    exit_image_path: str,
    output_path: str,
    label_entry: str = "Entrée",
    label_exit: str = "Sortie",
    target_height: int = 480,
) -> str:
    """Étape 4 — une image composite "entrée | sortie" par checkpoint en écart.

    Une seule image = un seul `Image()` reportlab à placer côté rendu,
    au lieu de deux flottants séparés mal alignés.
    """
    entry_img = PILImage.open(entry_image_path).convert("RGB")
    exit_img = PILImage.open(exit_image_path).convert("RGB")

    def _resize(img: PILImage.Image) -> PILImage.Image:
        ratio = target_height / img.height
        return img.resize((max(1, int(img.width * ratio)), target_height))

    entry_img = _resize(entry_img)
    exit_img = _resize(exit_img)

    separator_width = 6
    composite_width = entry_img.width + separator_width + exit_img.width
    composite = PILImage.new("RGB", (composite_width, target_height), color=(20, 20, 20))
    composite.paste(entry_img, (0, 0))
    composite.paste(exit_img, (entry_img.width + separator_width, 0))

    draw = ImageDraw.Draw(composite)
    try:
        font = ImageFont.truetype("Arial.ttf", 24)
    except OSError:
        font = ImageFont.load_default()

    for text, x in ((label_entry, 12), (label_exit, entry_img.width + separator_width + 12)):
        draw.rectangle([x - 6, 6, x + 8 * len(text), 34], fill=(0, 0, 0))
        draw.text((x, 8), text, fill=(255, 255, 255), font=font)

    composite.save(output_path)
    return output_path
