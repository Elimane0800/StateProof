"""
Agent D — Mode 1 (déterministe, Étape 1) + Mode 2 (raisonnement légal, Étape 2).

Mode 1 : une fonction pure, zéro LLM, testable en 10 minutes avec une grille
bidon — c'est exactement le mécanisme prévu par le décret quand une grille
contractuelle existe.

Mode 2 : un prompt LLM ancré sur les critères jurisprudentiels, pas sur des
chiffres inventés. Cas par défaut (aucune grille annexée au bail).
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
# Mode 1 — déterministe (grille de vétusté annexée au bail)
# ---------------------------------------------------------------------------

def apply_vetuste_grid(
    element_category: str,
    years_occupied: float,
    grid: VetusteGrid,
    estimated_cost_eur: float,
) -> LegalQualification:
    """Applique une grille de vétusté contractuelle. Pas de LLM ici, juste
    du calcul — légalement défendable puisque c'est exactement le mécanisme
    prévu par le décret n°2016-382 quand une grille existe."""
    entry = grid.get(element_category)
    if entry is None:
        return LegalQualification(
            legal_qualification="indetermine",
            responsibility="indetermine",
            legal_basis=[LEGAL_BASIS_VETUSTE_DECREE],
            grille_appliquee=False,
            reasoning=(
                f"Aucune entrée de grille pour la catégorie '{element_category}' : "
                "qualification impossible en Mode 1 (grille), retomber sur le Mode 2."
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
            f"Grille contractuelle appliquée pour '{element_category}' : "
            f"{years_occupied:.1f} an(s) d'occupation, franchise de "
            f"{entry.franchise_ans} an(s), taux d'abattement de "
            f"{entry.taux_annuel * 100:.1f}%/an -> abattement de "
            f"{abattement * 100:.1f}%."
        ),
        confidence=1.0,  # calcul déterministe, pas d'incertitude de modèle
    )


# ---------------------------------------------------------------------------
# Mode 2 — raisonnement légal par LLM (cas par défaut, pas de grille)
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
    """Qualifie un écart `damage` par analogie jurisprudentielle, sans
    chiffre inventé. Ne lève jamais d'exception : fallback "indetermine"."""
    llm = llm or _make_llm()

    element_category = (entry_node or exit_node).element_type if (entry_node or exit_node) else None
    prompt = build_qualification_prompt(
        element_category=element_category or edge.checkpoint_id,
        room=edge.room,
        occupancy_months=occupancy_months,
        defect_description=edge.reasoning,
        entry_condition=entry_node.properties.condition if entry_node else "inconnu",
        exit_condition=exit_node.properties.condition if exit_node else "inconnu",
    )

    last_error: Optional[str] = None
    for attempt in range(MAX_RETRIES + 1):
        user_message = prompt
        if attempt > 0 and last_error:
            user_message += (
                f"\n\nATTENTION : ta réponse précédente était invalide ({last_error}). "
                "Corrige et renvoie UNIQUEMENT le JSON attendu."
            )

        raw = llm.invoke_for_json(user_message)
        if raw is None:
            last_error = "réponse non parsable en JSON"
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
        reasoning="Qualification automatique indisponible — analyse manuelle requise.",
        confidence=0.0,
    )
