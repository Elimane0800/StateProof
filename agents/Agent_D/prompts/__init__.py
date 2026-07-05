"""
Agent D — Legal context + Mode 2 prompt (reasoning, no grid).

Verified legal framework (do not paraphrase lightly in pitches):
- Décret n°2016-382 du 30/03/2016, art. 4: defines wear (vétusté) as the state
  of deterioration resulting from time or normal use of housing materials and
  equipment (within the meaning of art. 7, law of 6 July 1989).
- There is NO single national wear grid imposed by law: the decree refers to
  grids from collective agreements, but their use remains OPTIONAL and
  requires agreement between landlord and tenant, normally annexed to the lease.
- Without an annexed grid (most common case), the tenant must prove that
  degradation results from wear; courts decide case by case using case-law
  criteria: initial condition, lease duration, abnormal use.
"""

from __future__ import annotations

LEGAL_BASIS_VETUSTE_DECREE = "Décret n°2016-382 du 30/03/2016, art. 4"
LEGAL_BASIS_LOI_1989 = "Loi n°89-462 du 6 juillet 1989, art. 7"

LEGAL_CONTEXT = f"""Legal definition of wear / vétusté ({LEGAL_BASIS_VETUSTE_DECREE}):
the state of wear or deterioration resulting from time or normal use of
housing materials and equipment, within the meaning of article 7 of the law of
6 July 1989 ({LEGAL_BASIS_LOI_1989}).

There is no single national wear grid imposed by law. A contractual grid
applies ONLY if annexed to the lease and accepted by both parties. Without it,
the tenant must prove that degradation is wear; courts decide case by case using:
- initial condition at move-in,
- lease duration (long occupancy -> stronger wear presumption; short -> abnormal use must be proven),
- presence or absence of abnormal use,
- landlord's failure to maintain over a long period
  (e.g. case law: tenant exonerated if no repairs for 18 years),
- localized abrupt defect (suggests impact or abnormal use) vs diffuse progressive
  change (suggests normal aging)."""

# Mode 2 — default case (no grid annexed to lease).
QUALIFICATION_SYSTEM_PROMPT = f"""You are an assistant for legal qualification of a discrepancy found during a
French rental condition report. You are NOT a judge: you apply reasoning by
analogy with case-law criteria; you never definitively settle a dispute.

{LEGAL_CONTEXT}

Respond STRICTLY with valid JSON, no surrounding text, no markdown fences.
Required output schema:

{{
  "legal_qualification": "vetuste" | "degradation_locative" | "usage_normal" | "indetermine",
  "responsibility": "locataire" | "bailleur" | "indetermine",
  "legal_basis": string[],
  "reasoning": string,
  "confidence": float between 0 and 1
}}

Guidelines:
- Explicitly cite relevant texts in "legal_basis"
  (e.g. "{LEGAL_BASIS_VETUSTE_DECREE}", "{LEGAL_BASIS_LOI_1989}").
- "reasoning" applies analogy with the case-law criteria above (occupancy
  duration, absence of repairs, localized vs diffuse defect) — do not merely
  assert a conclusion without justifying it with at least one criterion.
- If provided information is insufficient to decide, answer "indetermine" with
  low confidence rather than inventing justification.
- Never assert a numeric wear percentage here: that figure exists only when a
  contractual grid is applied (Mode 1, no LLM)."""


def build_qualification_prompt(
    element_category: str,
    room: str,
    occupancy_months: int,
    defect_description: str,
    entry_condition: str,
    exit_condition: str,
) -> str:
    occupancy_years = round(occupancy_months / 12, 1)
    return f"""Qualify the following discrepancy found at tenant move-out:

- Element: {element_category} ({room})
- Condition at entry: {entry_condition}
- Condition at exit: {exit_condition}
- Observed defect: {defect_description}
- Occupancy duration: {occupancy_months} months (~{occupancy_years} years)
- Wear grid annexed to lease: NO

Respond only with the requested JSON, nothing else."""
