"""Agent B — State partagé par le graphe LangGraph d'alignement entrée/sortie."""

from __future__ import annotations

from typing import List, TypedDict

from agents.common.schemas import AlignmentEdge, Graph


class AlignmentState(TypedDict, total=False):
    # Entrées
    entry_graph: Graph
    exit_graph: Graph

    # Sorties
    edges: List[AlignmentEdge]
    confidence_score: float
