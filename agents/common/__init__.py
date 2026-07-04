"""
ARIA — Structures de données partagées entre les modules A, B, C, D.

C'est le point de jonction : chaque module ne dépend QUE de ces schémas,
jamais de l'implémentation interne des autres modules.
"""

from agents.common.schemas import (
    CheckpointDef,
    RoomConfig,
    PropertyConfig,
    NodeProperties,
    Node,
    EdgeType,
    StructuralEdge,
    Graph,
    AlignmentStatus,
    Severity,
    AlignmentEdge,
    VetusteGridEntry,
    LegalQualification,
    SummaryRow,
    DetailedSection,
    ReportData,
)

__all__ = [
    "CheckpointDef",
    "RoomConfig",
    "PropertyConfig",
    "NodeProperties",
    "Node",
    "EdgeType",
    "StructuralEdge",
    "Graph",
    "AlignmentStatus",
    "Severity",
    "AlignmentEdge",
    "VetusteGridEntry",
    "LegalQualification",
    "SummaryRow",
    "DetailedSection",
    "ReportData",
]
