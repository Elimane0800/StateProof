"""
Agent B — Detection / alignment module (steps 3 + 5).

Goal: take entry_graph and exit_graph (same node structure, by construction — same
checkpoint config) and produce the list of classified divergences + a global
confidence score.

Recommended code order: prompts (1, tested in isolation) -> nodes.compare_node (2)
-> this file: align (3) -> prompt iteration on technical_noise (4, in prompts)
-> compute_confidence_score (5, pure, no LLM).
"""

from __future__ import annotations

from typing import List

from langgraph.graph import END, StateGraph

from agents.Agent_B.nodes import compare_node
from agents.Agent_B.state import AlignmentState
from agents.common.schemas import AlignmentEdge, Graph, Severity

# Severity weighting in the global confidence score (step 5).
# Deliberately simple, explainable formula: "severity-weighted average of each
# edge's confidence".
SEVERITY_WEIGHTS = {
    Severity.NONE: 0.5,
    Severity.LOW: 1.0,
    Severity.MEDIUM: 2.0,
    Severity.HIGH: 3.0,
}


def align(entry_graph: Graph, exit_graph: Graph) -> List[AlignmentEdge]:
    """Compare each common checkpoint across both graphs.

    No matching problem to solve: by construction, `id`s are the same (same
    checkpoint config for entry and exit) — a simple loop, not graph matching.
    """
    common_ids = entry_graph.checkpoint_node_ids() & exit_graph.checkpoint_node_ids()

    edges: List[AlignmentEdge] = []
    for node_id in sorted(common_ids):
        entry_node = entry_graph.get_node(node_id)
        exit_node = exit_graph.get_node(node_id)
        edges.append(compare_node(entry_node, exit_node))

    return edges


def compute_confidence_score(edges: List[AlignmentEdge]) -> float:
    """Severity-weighted average of each edge's `confidence`.

    Pure function, no LLM. This is the figure on the PDF cover page (Module C) —
    the formula must stay simple and explainable.
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
# Optional LangGraph orchestration — consistent with Agent_A
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
    # Example: Module B testable with hand-written Nodes while Module A is not
    # ready yet (mock, see junction point).
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
