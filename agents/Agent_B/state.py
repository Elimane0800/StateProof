"""Agent B — Shared state for the entry/exit alignment LangGraph."""

from __future__ import annotations

from typing import List, TypedDict

from agents.common.schemas import AlignmentEdge, Graph


class AlignmentState(TypedDict, total=False):
    # Inputs
    entry_graph: Graph
    exit_graph: Graph

    # Outputs
    edges: List[AlignmentEdge]
    confidence_score: float
