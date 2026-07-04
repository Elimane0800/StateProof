"""
Agent A — Prompts (Étape 2 du plan de construction).

Deux modes, deux prompts :
- Mode "un checkpoint par image" (build_state_description_prompt) : une image
  + un checkpoint_id. C'est la brique la plus facile à valider isolément.
- Mode "plusieurs checkpoints par image" (build_multi_checkpoint_prompt) :
  une seule photo peut montrer PLUSIEURS éléments à inspecter (ex : une photo
  d'extérieur de véhicule montre pare-choc + portière + jante + pare-brise
  en même temps). Le VLM doit alors identifier CHAQUE élément demandé,
  décrire son état ET le localiser (bbox_pct) pour que le Module B sache
  ensuite où regarder sans confondre deux checkpoints voisins.
"""

from __future__ import annotations

import json
from typing import List, Optional

STATE_DESCRIPTION_SYSTEM_PROMPT = """Tu es un expert en état des lieux immobilier.
Ta tâche : décrire objectivement l'état d'UN SEUL élément visible sur une photo
(un mur, un sol, une prise électrique...), pour constituer un constat d'état
initial ou final.

Réponds STRICTEMENT avec un JSON valide, sans texte autour, sans balises
markdown, sans commentaire. Schéma de sortie obligatoire :

{
  "material": string | null,
  "color": string | null,
  "condition": "intact" | "usé" | "endommagé" | "unknown",
  "defects": string[],
  "confidence": float entre 0 et 1
}

Consignes :
- Base-toi UNIQUEMENT sur ce que tu observes réellement sur l'image fournie.
- Si l'élément demandé est masqué, flou, hors cadre ou absent, mets
  "condition": "unknown" et une "confidence" basse (< 0.3).
- "defects" liste les anomalies visibles (fissure, tache, trou, brûlure,
  auréole, éclat...). Liste vide si aucune anomalie visible.
- "confidence" reflète ta certitude sur l'ensemble de la description, pas
  uniquement sur l'état.
- N'invente jamais de détail non observable (ex : ne devine pas un matériau
  caché par un meuble)."""


def build_state_description_prompt(
    checkpoint_id: str,
    element_type: str | None = None,
    room: str | None = None,
) -> str:
    """Construit le message utilisateur associé à une image de checkpoint."""
    hints = []
    if room:
        hints.append(f"Pièce : {room}")
    if element_type:
        hints.append(f"Type d'élément attendu : {element_type}")
    hints.append(f"Identifiant du checkpoint : {checkpoint_id}")

    return (
        "Décris l'état de l'élément visible sur cette image, en te limitant "
        "à l'élément identifié ci-dessous.\n"
        + "\n".join(hints)
        + "\n\nRéponds uniquement avec le JSON demandé, rien d'autre."
    )


# ---------------------------------------------------------------------------
# Mode multi-checkpoints : une image, plusieurs éléments à décrire + localiser
# ---------------------------------------------------------------------------

MULTI_CHECKPOINT_SYSTEM_PROMPT = """Tu es un expert en constat d'état (immobilier ou véhicule).
Ta tâche : sur UNE SEULE photo montrant PLUSIEURS éléments distincts, décrire
objectivement l'état de CHACUN des éléments demandés, et LOCALISER chacun
d'eux sur l'image.

Réponds STRICTEMENT avec un JSON valide, sans texte autour, sans balises
markdown, sans commentaire. Schéma de sortie obligatoire : un objet JSON dont
les clés sont EXACTEMENT les identifiants de checkpoint fournis, et dont
chaque valeur suit ce schéma :

{
  "<checkpoint_id>": {
    "visible": bool,
    "material": string | null,
    "color": string | null,
    "condition": "intact" | "usé" | "endommagé" | "unknown",
    "defects": string[],
    "confidence": float entre 0 et 1,
    "bbox_pct": [x_min, y_min, x_max, y_max] | null
  },
  ...
}

Consignes :
- Traite CHAQUE checkpoint demandé indépendamment des autres, mais utilise le
  contexte global de l'image pour bien identifier lequel est lequel (ex : ne
  confonds pas l'aile avant droite avec la portière avant droite).
- "visible" = false si l'élément demandé n'apparaît pas du tout sur cette
  photo (hors-cadre, masqué) ; dans ce cas mets "condition": "unknown",
  "confidence": 0.0, "bbox_pct": null, "defects": [].
- "bbox_pct" localise l'élément en coordonnées normalisées entre 0 et 1
  (0,0 = coin haut-gauche, 1,1 = coin bas-droit), format
  [x_min, y_min, x_max, y_max]. Il doit cibler la zone la plus ÉTROITE
  possible qui contient réellement l'élément (pas toute la photo). Mets null
  uniquement si "visible" est false.
- "defects" liste les anomalies visibles sur CET élément (rayure, bosse,
  fissure, tache, impact, usure...). Liste vide si aucune anomalie visible.
- N'invente jamais un détail non observable. Base-toi uniquement sur ce que
  tu vois réellement sur l'image fournie.
- Réponds pour TOUS les checkpoints demandés, même ceux non visibles."""


def build_multi_checkpoint_prompt(
    checkpoints: List["CheckpointDef"],  # noqa: F821 - éviter l'import circulaire, cf. common.schemas
    room: Optional[str] = None,
) -> str:
    """Construit le message utilisateur listant tous les checkpoints attendus
    sur cette image (une photo = potentiellement plusieurs éléments)."""
    items = []
    for cp in checkpoints:
        cp_id = cp.id if hasattr(cp, "id") else cp
        cp_type = getattr(cp, "element_type", None)
        items.append({"checkpoint_id": cp_id, "type_attendu": cp_type})

    header = f"Zone photographiée : {room}\n" if room else ""
    return (
        header
        + "Voici la liste des éléments à identifier, décrire et localiser sur "
        "cette image :\n"
        + json.dumps(items, indent=2, ensure_ascii=False)
        + "\n\nRéponds uniquement avec l'objet JSON demandé (une clé par "
        "checkpoint_id ci-dessus), rien d'autre."
    )
