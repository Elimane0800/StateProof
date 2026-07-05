"""
Agent D — Mode 1 (deterministic, step 1) + Mode 2 (legal reasoning, step 2).

Mode 1: a pure function, zero LLM, testable in 10 minutes with a dummy grid —
exactly the mechanism foreseen by the decree when a contractual grid exists.

Mode 2: an LLM prompt anchored on case-law criteria, not invented figures.
Default case (no grid annexed to lease).
"""

from __future__ import annotations

from typing import Optional

from pydantic import ValidationError

from agents.base_model.base_llm_nim import BaseLLMProvider, DEFAULT_MODEL
from agents.common.schemas import (
    AlignmentEdge,
    LegalQualification,
    Node,
    VetusteGrid,
)
from agents.Agent_D.prompts import (
    LEGAL_BASIS_VETUSTE_DECREE,
    QUALIFICATION_SYSTEM_PROMPT,
    build_qualification_prompt,
)

MAX_RETRIES = 1


# ---------------------------------------------------------------------------
# Mode 1 — deterministic (wear grid annexed to lease)
# ---------------------------------------------------------------------------

def apply_vetuste_grid(
    element_category: str,
    years_occupied: float,
    grid: VetusteGrid,
    estimated_cost_eur: float,
) -> LegalQualification:
    """Apply a contractual wear grid. No LLM here — legally defensible since it
    is exactly the mechanism foreseen by decree n°2016-382 when a grid exists."""
    entry = grid.get(element_category)
    if entry is None:
        return LegalQualification(
            legal_qualification="indetermine",
            responsibility="indetermine",
            legal_basis=[LEGAL_BASIS_VETUSTE_DECREE],
            grille_appliquee=False,
            reasoning=(
                f"No grid entry for category '{element_category}': "
                "qualification impossible in Mode 1 (grid); fall back to Mode 2."
            ),
            confidence=0.0,
        )

    years_depreciable = max(0.0, years_occupied - entry.franchise_ans)
    abattement = min(1.0, years_depreciable * entry.taux_annuel)
    chargeable = round(estimated_cost_eur * (1 - abattement), 2)

    return LegalQualification(
        legal_qualification="vetuste" if abattement > 0 else "degradation_locative",
        responsibility="locataire" if chargeable > 0 else "indetermine",
        legal_basis=[LEGAL_BASIS_VETUSTE_DECREE, "Grille de vétusté annexée au bail"],
        grille_appliquee=True,
        abattement_pct=round(abattement * 100, 1),
        chargeable_amount_eur=chargeable,
        reasoning=(
            f"Contractual grid applied for '{element_category}': "
            f"{years_occupied:.1f} year(s) of occupancy, franchise of "
            f"{entry.franchise_ans} year(s), deduction rate of "
            f"{entry.taux_annuel * 100:.1f}%/year -> deduction of "
            f"{abattement * 100:.1f}%."
        ),
        confidence=1.0,  # deterministic calculation, no model uncertainty
    )


# ---------------------------------------------------------------------------
# Mode 2 — legal reasoning by LLM (default case, no grid)
# ---------------------------------------------------------------------------

def _make_llm() -> BaseLLMProvider:
    return BaseLLMProvider(
        system_prompt=QUALIFICATION_SYSTEM_PROMPT,
        model_name=DEFAULT_MODEL,
        temperature=0.1,
    )


def qualify_with_llm(
    edge: AlignmentEdge,
    occupancy_months: int,
    entry_node: Optional[Node] = None,
    exit_node: Optional[Node] = None,
    llm: Optional[BaseLLMProvider] = None,
) -> LegalQualification:
    """Qualify a `damage` edge by case-law analogy, without invented figures.
    Never raises: fallback "indetermine"."""
    llm = llm or _make_llm()

    element_category = (entry_node or exit_node).element_type if (entry_node or exit_node) else None
    prompt = build_qualification_prompt(
        element_category=element_category or edge.checkpoint_id,
        room=edge.room,
        occupancy_months=occupancy_months,
        defect_description=edge.reasoning,
        entry_condition=entry_node.properties.condition if entry_node else "unknown",
        exit_condition=exit_node.properties.condition if exit_node else "unknown",
    )

    last_error: Optional[str] = None
    for attempt in range(MAX_RETRIES + 1):
        user_message = prompt
        if attempt > 0 and last_error:
            user_message += (
                f"\n\nWARNING: your previous response was invalid ({last_error}). "
                "Fix it and return ONLY the expected JSON."
            )

        raw = llm.invoke_for_json(user_message)
        if raw is None:
            last_error = "response not parseable as JSON"
            continue

        try:
            return LegalQualification(
                legal_qualification=raw["legal_qualification"],
                responsibility=raw["responsibility"],
                legal_basis=raw.get("legal_basis", []),
                grille_appliquee=False,
                abattement_pct=None,
                chargeable_amount_eur=edge.estimated_cost_eur,
                reasoning=raw.get("reasoning", ""),
                confidence=raw.get("confidence", 0.0),
            )
        except (ValidationError, KeyError) as e:
            last_error = str(e)
            continue

    return LegalQualification(
        legal_qualification="indetermine",
        responsibility="indetermine",
        legal_basis=[],
        grille_appliquee=False,
        chargeable_amount_eur=edge.estimated_cost_eur,
        reasoning="Automatic qualification unavailable — manual review required.",
        confidence=0.0,
    )
