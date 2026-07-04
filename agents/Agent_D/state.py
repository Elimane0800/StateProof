"""Agent D — State partagé par le graphe LangGraph de qualification légale."""

from __future__ import annotations

from typing import Optional, TypedDict

from agents.common.schemas import AlignmentEdge, LegalQualification, Node, VetusteGrid


class QualificationState(TypedDict, total=False):
    # Entrées
    edge: AlignmentEdge
    occupancy_months: int
    element_category: Optional[str]
    grid: Optional[VetusteGrid]
    entry_node: Optional[Node]
    exit_node: Optional[Node]

    # Sortie
    qualification: LegalQualification
