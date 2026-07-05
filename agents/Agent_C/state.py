"""Agent C — Shared state for the PDF generation pipeline."""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict

from agents.common.schemas import AlignmentEdge, Graph, LegalQualification, ReportData


class ReportState(TypedDict, total=False):
    # Inputs (data contract only — Module C ignores how they were computed)
    entry_graph: Graph
    exit_graph: Graph
    edges: List[AlignmentEdge]
    confidence_score: float
    legal_qualifications: Dict[str, LegalQualification]
    address: Optional[str]
    entry_date: Optional[str]
    exit_date: Optional[str]
    output_path: str

    # Outputs
    report_data: ReportData
    pdf_path: str
