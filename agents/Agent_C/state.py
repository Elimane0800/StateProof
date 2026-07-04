"""Agent C — State partagé par le pipeline de génération du PDF."""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict

from agents.common.schemas import AlignmentEdge, Graph, LegalQualification, ReportData


class ReportState(TypedDict, total=False):
    # Entrées (contrat de données uniquement — Module C ignore comment elles ont été calculées)
    entry_graph: Graph
    exit_graph: Graph
    edges: List[AlignmentEdge]
    confidence_score: float
    legal_qualifications: Dict[str, LegalQualification]
    address: Optional[str]
    entry_date: Optional[str]
    exit_date: Optional[str]
    output_path: str

    # Sorties
    report_data: ReportData
    pdf_path: str
