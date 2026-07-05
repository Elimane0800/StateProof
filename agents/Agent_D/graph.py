"""
Agent D — Legal qualification (wear vs abnormal use), steps 3 & 4.

qualify(edge, occupancy_months, grid=None) -> LegalQualification chooses the mode
based on `grid` presence:
  - Mode 1 (deterministic) if a wear grid is provided and covers the element category.
  - Mode 2 (LLM reasoning by case-law analogy) otherwise.

The `disclaimer` (on `LegalQualification`, default in the common schema) must be
reflected in the final PDF (Module C), not only in JSON — see
agents.Agent_C.prompts.LEGAL_DISCLAIMER.
"""

from __future__ import annotations

from typing import Optional

from langgraph.graph import END, StateGraph

from agents.Agent_D.nodes import apply_vetuste_grid, qualify_with_llm
from agents.Agent_D.state import QualificationState
from agents.common.schemas import AlignmentEdge, LegalQualification, Node, VetusteGrid


def qualify(
    edge: AlignmentEdge,
    occupancy_months: int,
    element_category: Optional[str] = None,
    grid: Optional[VetusteGrid] = None,
    entry_node: Optional[Node] = None,
    exit_node: Optional[Node] = None,
) -> LegalQualification:
    """Single entry point for Module D. Only qualifies relevant divergences:
    `unchanged` has nothing to qualify legally."""
    if edge.status == "unchanged":
        return LegalQualification(
            legal_qualification="usage_normal",
            responsibility="indetermine",
            reasoning="No divergence observed; legal qualification not applicable.",
            confidence=1.0,
        )

    reference_node = entry_node or exit_node
    category = element_category or (reference_node.element_type if reference_node else None)

    if grid is not None and category is not None and category in grid:
        years_occupied = occupancy_months / 12
        return apply_vetuste_grid(category, years_occupied, grid, edge.estimated_cost_eur)

    return qualify_with_llm(edge, occupancy_months, entry_node=entry_node, exit_node=exit_node)


# ---------------------------------------------------------------------------
# Optional LangGraph orchestration — conditional Mode 1 / Mode 2 routing
# ---------------------------------------------------------------------------

def _route(state: QualificationState) -> str:
    category = state.get("element_category")
    grid = state.get("grid")
    if grid is not None and category is not None and category in grid:
        return "mode1_grid"
    return "mode2_llm"


def _mode1_step(state: QualificationState) -> QualificationState:
    years_occupied = state["occupancy_months"] / 12
    result = apply_vetuste_grid(
        state["element_category"], years_occupied, state["grid"], state["edge"].estimated_cost_eur
    )
    return {**state, "qualification": result}


def _mode2_step(state: QualificationState) -> QualificationState:
    result = qualify_with_llm(
        state["edge"], state["occupancy_months"],
        entry_node=state.get("entry_node"), exit_node=state.get("exit_node"),
    )
    return {**state, "qualification": result}


def compile_agent_d_graph():
    workflow = StateGraph(QualificationState)
    workflow.add_node("mode1_grid", _mode1_step)
    workflow.add_node("mode2_llm", _mode2_step)
    workflow.set_conditional_entry_point(_route, {"mode1_grid": "mode1_grid", "mode2_llm": "mode2_llm"})
    workflow.add_edge("mode1_grid", END)
    workflow.add_edge("mode2_llm", END)
    return workflow.compile()


if __name__ == "__main__":
    import json

    from agents.common.schemas import AlignmentEdge, VetusteGridEntry

    edge = AlignmentEdge(
        node_id="salon:mur_nord", checkpoint_id="mur_nord", room="salon",
        status="damage", severity="high", confidence=0.91,
        reasoning="Localized impact incompatible with normal aging.",
        estimated_cost_eur=45,
    )

    # Mode 1 — with grid
    grid = {"mur": VetusteGridEntry(duree_vie_ans=10, franchise_ans=1, taux_annuel=0.10)}
    result_mode1 = qualify(edge, occupancy_months=36, element_category="mur", grid=grid)
    print("Mode 1:", json.dumps(result_mode1.model_dump(), indent=2, ensure_ascii=False))

    # Mode 2 — without grid (requires NVIDIA_API_KEY for a real LLM call)
    # result_mode2 = qualify(edge, occupancy_months=36, element_category="mur")
    # print("Mode 2:", json.dumps(result_mode2.model_dump(), indent=2, ensure_ascii=False))
