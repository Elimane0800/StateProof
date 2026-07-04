"""Agent B — Détection / alignement entrée-sortie (list[AlignmentEdge] + score de confiance)."""

from agents.Agent_B.graph import align, compile_agent_b_graph, compute_confidence_score
from agents.Agent_B.nodes import compare_node
from agents.Agent_B.visualize import annotate_divergence

__all__ = [
    "align",
    "compile_agent_b_graph",
    "compute_confidence_score",
    "compare_node",
    "annotate_divergence",
]
