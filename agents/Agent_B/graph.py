"""
Agent B — Module de détection / alignement (Étape 3 + Étape 5).

But : prendre entry_graph et exit_graph (même structure de nœuds, par
construction — même config de checkpoints) et produire la liste des écarts
classifiés + un score de confiance global.

Ordre de code recommandé : prompts (1, testé isolément) -> nodes.compare_node (2)
-> ce fichier: align (3) -> itération prompt sur technical_noise (4, dans prompts)
-> compute_confidence_score (5, pure, sans LLM).
"""

from __future__ import annotations

from typing import List

from langgraph.graph import END, StateGraph

from agents.Agent_B.nodes import compare_node
from agents.Agent_B.state import AlignmentState
from agents.common.schemas import AlignmentEdge, Graph, Severity

# Pondération de la sévérité dans le score de confiance global (Étape 5).
# Formule volontairement simple et explicable en une phrase : "moyenne
# pondérée par sévérité des confidences de chaque arête".
SEVERITY_WEIGHTS = {
    Severity.NONE: 0.5,
    Severity.LOW: 1.0,
    Severity.MEDIUM: 2.0,
    Severity.HIGH: 3.0,
}


def align(entry_graph: Graph, exit_graph: Graph) -> List[AlignmentEdge]:
    """Compare chaque checkpoint commun aux deux graphes.

    Aucun problème de correspondance à résoudre : par construction, les
    `id` sont les mêmes (même config de checkpoints pour l'entrée et la
    sortie) — c'est une simple boucle, pas du matching de graphe.
    """
    common_ids = entry_graph.checkpoint_node_ids() & exit_graph.checkpoint_node_ids()

    edges: List[AlignmentEdge] = []
    for node_id in sorted(common_ids):
        entry_node = entry_graph.get_node(node_id)
        exit_node = exit_graph.get_node(node_id)
        edges.append(compare_node(entry_node, exit_node))

    return edges


def compute_confidence_score(edges: List[AlignmentEdge]) -> float:
    """Moyenne pondérée par sévérité des `confidence` de chaque arête.

    Fonction pure, sans LLM. C'est le chiffre affiché en page de garde du
    rapport PDF (Module C) — la formule doit rester simple et explicable.
    """
    if not edges:
        return 0.0

    weighted_sum = 0.0
    total_weight = 0.0
    for edge in edges:
        weight = SEVERITY_WEIGHTS.get(edge.severity, 1.0)
        weighted_sum += weight * edge.confidence
        total_weight += weight

    if total_weight == 0:
        return 0.0
    return round(weighted_sum / total_weight, 4)


# ---------------------------------------------------------------------------
# Orchestration LangGraph (optionnelle) — homogène avec Agent_A
# ---------------------------------------------------------------------------

def _align_step(state: AlignmentState) -> AlignmentState:
    edges = align(state["entry_graph"], state["exit_graph"])
    return {**state, "edges": edges}


def _score_step(state: AlignmentState) -> AlignmentState:
    score = compute_confidence_score(state["edges"])
    return {**state, "confidence_score": score}


def compile_agent_b_graph():
    workflow = StateGraph(AlignmentState)
    workflow.add_node("align", _align_step)
    workflow.add_node("compute_confidence_score", _score_step)
    workflow.set_entry_point("align")
    workflow.add_edge("align", "compute_confidence_score")
    workflow.add_edge("compute_confidence_score", END)
    return workflow.compile()


if __name__ == "__main__":
    # Exemple : Module B testable avec des Node écrits à la main pendant que
    # le Module A n'est pas encore prêt (mock, cf. point de jonction).
    from agents.common.schemas import Node, NodeProperties

    entry = Graph(
        property_id="appt-12",
        nodes={
            "salon:mur_nord": Node(
                id="salon:mur_nord",
                checkpoint_id="mur_nord",
                room="salon",
                properties=NodeProperties(material="plâtre peint", color="blanc", condition="intact", confidence=0.94),
            )
        },
    )
    exit_ = Graph(
        property_id="appt-12",
        nodes={
            "salon:mur_nord": Node(
                id="salon:mur_nord",
                checkpoint_id="mur_nord",
                room="salon",
                properties=NodeProperties(material="plâtre peint", color="blanc", condition="endommagé", defects=["trou"], confidence=0.9),
            )
        },
    )
    result_edges = align(entry, exit_)
    print([e.model_dump() for e in result_edges])
    print("score:", compute_confidence_score(result_edges))
