"""
Agent D — Qualification légale (vétusté vs usage anormal), Étapes 3 & 4.

qualify(edge, occupancy_months, grid=None) -> LegalQualification choisit le
mode selon la présence de `grid` :
  - Mode 1 (déterministe) si une grille de vétusté est fournie et couvre la
    catégorie d'élément concernée.
  - Mode 2 (raisonnement LLM par analogie jurisprudentielle) sinon.

Le `disclaimer` (porté par `LegalQualification`, valeur par défaut dans le
schéma commun) doit être répercuté dans le PDF final (Module C), pas
seulement dans le JSON — voir agents.Agent_C.prompts.LEGAL_DISCLAIMER.
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
    """Point d'entrée unique du Module D. Ne qualifie que les écarts
    pertinents : `unchanged` n'a rien à qualifier légalement."""
    if edge.status == "unchanged":
        return LegalQualification(
            legal_qualification="usage_normal",
            responsibility="indetermine",
            reasoning="Aucun écart constaté, qualification légale non applicable.",
            confidence=1.0,
        )

    reference_node = entry_node or exit_node
    category = element_category or (reference_node.element_type if reference_node else None)

    if grid is not None and category is not None and category in grid:
        years_occupied = occupancy_months / 12
        return apply_vetuste_grid(category, years_occupied, grid, edge.estimated_cost_eur)

    return qualify_with_llm(edge, occupancy_months, entry_node=entry_node, exit_node=exit_node)


# ---------------------------------------------------------------------------
# Orchestration LangGraph (optionnelle) — routage conditionnel Mode 1 / Mode 2
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
        reasoning="Impact localisé incompatible avec un vieillissement normal.",
        estimated_cost_eur=45,
    )

    # Mode 1 — avec grille
    grid = {"mur": VetusteGridEntry(duree_vie_ans=10, franchise_ans=1, taux_annuel=0.10)}
    result_mode1 = qualify(edge, occupancy_months=36, element_category="mur", grid=grid)
    print("Mode 1 :", json.dumps(result_mode1.model_dump(), indent=2, ensure_ascii=False))

    # Mode 2 — sans grille (nécessite NVIDIA_API_KEY pour un vrai appel LLM)
    # result_mode2 = qualify(edge, occupancy_months=36, element_category="mur")
    # print("Mode 2 :", json.dumps(result_mode2.model_dump(), indent=2, ensure_ascii=False))
