"""
Agent D — Contexte légal + prompt du Mode 2 (raisonnement, pas de grille).

Cadre légal vérifié (à ne pas paraphraser à la légère en pitch) :
- Décret n°2016-382 du 30/03/2016, art. 4 : définit la vétusté comme l'état
  d'usure ou de détérioration résultant du temps ou de l'usage normal des
  matériaux et équipements du logement (au sens de l'art. 7, loi du
  6 juillet 1989).
- Il n'existe PAS de grille de vétusté nationale unique imposée par la loi :
  le décret renvoie vers des grilles issues d'accords collectifs, mais leur
  usage reste FACULTATIF et suppose un accord entre bailleur et locataire,
  en principe annexé au bail.
- En l'absence de grille annexée (cas le plus fréquent), c'est au locataire
  de prouver que la dégradation résulte de la vétusté ; les tribunaux
  tranchent au cas par cas selon des critères jurisprudentiels : état
  initial du logement, durée de la location, existence d'un usage anormal.
"""

from __future__ import annotations

LEGAL_BASIS_VETUSTE_DECREE = "Décret n°2016-382 du 30/03/2016, art. 4"
LEGAL_BASIS_LOI_1989 = "Loi n°89-462 du 6 juillet 1989, art. 7"

LEGAL_CONTEXT = f"""Définition légale de la vétusté ({LEGAL_BASIS_VETUSTE_DECREE}) :
l'état d'usure ou de détérioration résultant du temps ou de l'usage normal
des matériaux et éléments d'équipement du logement, au sens de l'article 7
de la loi du 6 juillet 1989 ({LEGAL_BASIS_LOI_1989}).

Il n'existe pas de grille de vétusté nationale unique imposée par la loi.
Une grille contractuelle ne s'applique QUE si elle a été annexée au bail et
acceptée par les deux parties. En son absence, c'est au locataire de
prouver que la dégradation relève de la vétusté ; les tribunaux tranchent
au cas par cas selon des critères jurisprudentiels :
- l'état initial du logement constaté à l'entrée dans les lieux,
- la durée de la location (occupation longue -> présomption de vétusté
  plus forte ; occupation courte -> il faut prouver un usage anormal),
- l'existence ou non d'un usage anormal du bien,
- l'absence de travaux d'entretien par le bailleur sur une longue période
  (ex. jurisprudence : exonération du locataire si aucun travaux pendant
  18 ans),
- le caractère localisé et brutal d'un défaut (plutôt révélateur d'un choc
  ou d'un usage anormal) versus diffus et progressif (plutôt révélateur
  d'un vieillissement normal)."""

# Mode 2 — cas par défaut (pas de grille annexée au bail).
QUALIFICATION_SYSTEM_PROMPT = f"""Tu es un assistant d'aide à la qualification juridique
d'un écart constaté lors d'un état des lieux locatif en France. Tu n'es PAS
un juge : tu appliques un raisonnement par analogie avec des critères
jurisprudentiels, tu ne tranches jamais un litige de manière définitive.

{LEGAL_CONTEXT}

Réponds STRICTEMENT avec un JSON valide, sans texte autour, sans balises
markdown. Schéma de sortie obligatoire :

{{
  "legal_qualification": "vetuste" | "degradation_locative" | "usage_normal" | "indetermine",
  "responsibility": "locataire" | "bailleur" | "indetermine",
  "legal_basis": string[],
  "reasoning": string,
  "confidence": float entre 0 et 1
}}

Consignes :
- Cite explicitement dans "legal_basis" les textes pertinents
  (ex: "{LEGAL_BASIS_VETUSTE_DECREE}", "{LEGAL_BASIS_LOI_1989}").
- "reasoning" applique le raisonnement par analogie avec les critères
  jurisprudentiels ci-dessus (durée d'occupation, absence de travaux,
  caractère localisé vs diffus du défaut) — ne te contente pas d'affirmer
  une conclusion sans la justifier par au moins un de ces critères.
- Si les informations fournies sont insuffisantes pour trancher, réponds
  "indetermine" avec une confidence basse plutôt que d'inventer une
  justification.
- N'affirme jamais un pourcentage de vétusté chiffré ici : ce chiffre
  n'existe que si une grille contractuelle est appliquée (Mode 1,
  hors LLM)."""


def build_qualification_prompt(
    element_category: str,
    room: str,
    occupancy_months: int,
    defect_description: str,
    entry_condition: str,
    exit_condition: str,
) -> str:
    occupancy_years = round(occupancy_months / 12, 1)
    return f"""Qualifie l'écart suivant, constaté lors de la sortie d'un locataire :

- Élément : {element_category} ({room})
- État à l'entrée : {entry_condition}
- État à la sortie : {exit_condition}
- Défaut constaté : {defect_description}
- Durée d'occupation : {occupancy_months} mois (~{occupancy_years} ans)
- Grille de vétusté annexée au bail : NON

Réponds uniquement avec le JSON demandé, rien d'autre."""
