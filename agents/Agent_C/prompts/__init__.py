"""
Agent C — Pas de prompt LLM ici (zéro appel LLM dans tout le module C).

On garde ce fichier pour la cohérence de structure avec les autres agents,
et on y met les textes statiques du rapport (labels, méthodologie, disclaimer)
pour ne pas les disperser dans le code de rendu.
"""

from __future__ import annotations

STATUS_LABELS = {
    "unchanged": "Inchangé",
    "normal_wear": "Usure normale (vétusté)",
    "damage": "Dégradation",
    "evolution": "Évolution neutre",
}

SEVERITY_LABELS = {
    "none": "—",
    "low": "Faible",
    "medium": "Moyenne",
    "high": "Élevée",
}

# Étape 5 — présentation du score, sans sur-promettre : une phrase de méthode
# en petit texte, pas de fausse précision.
CONFIDENCE_SCORE_CAPTION = (
    "Score calculé comme la moyenne pondérée par sévérité de la confiance "
    "du modèle sur l'ensemble des points de contrôle. Un score élevé "
    "reflète la cohérence des observations, pas une garantie d'exactitude."
)

# Rappelé en pied de chaque page contenant des éléments de qualification légale.
LEGAL_DISCLAIMER = (
    "Analyse indicative générée par IA. Ne remplace pas une expertise "
    "contradictoire ou un avis juridique. En l'absence de grille de vétusté "
    "annexée au bail, la qualification s'appuie sur un raisonnement par "
    "analogie avec les critères jurisprudentiels usuels."
)

MISSING_DATA_LABEL = "Donnée non disponible"
