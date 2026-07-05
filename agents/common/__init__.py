"""
ARIA — Shared data structures between modules A, B, C, D.

This is the junction point: each module depends ONLY on these schemas, never on
other modules' internal implementation.
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
