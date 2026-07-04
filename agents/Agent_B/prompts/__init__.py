"""
Agent B — Prompts (Étape 1 + Étape 4 du plan de construction).

Comparaison d'UNE paire de nœuds à la fois. Le VLM hébergé (NIM) n'accepte
qu'UNE SEULE image par requête (contrainte serveur, pas un choix arbitraire)
— on lui fournit donc uniquement l'image de SORTIE, et les deux `properties`
déjà extraites par le Module A (texte) pour le contexte "avant". C'est aussi
sur cette image de sortie que se fait la localisation `bbox_pct`.

Cet appel n'est fait QUE si les `properties` entrée/sortie diffèrent — voir
agents.Agent_B.nodes._properties_equal : si elles sont identiques, le
statut "unchanged" est déterminé en pur Python, sans LLM (Module A a déjà
fait tout le travail de description).

Étape 4 (le "taste") : le few-shot ci-dessous couvre le cas `technical_noise`
— changement visible qui n'est PAS une dégradation (décoloration solaire,
angle de photo différent...). C'est le seul endroit du Module B où l'on
itère plusieurs fois sur le prompt.
"""

from __future__ import annotations

import json
from typing import Any, Dict

# Figé dès maintenant : tout le reste (couleurs Studio, filtres PDF) en dépend.
ALIGNMENT_STATUSES = ["unchanged", "normal_wear", "damage", "evolution"]
SEVERITIES = ["none", "low", "medium", "high"]

COMPARISON_SYSTEM_PROMPT = """Tu es un expert en constat d'état comparatif (entrée vs sortie — bien
immobilier ou véhicule).
Ta tâche : qualifier l'écart pour UN SEUL élément entre l'entrée et la sortie.
Tu ne reçois QU'UNE SEULE IMAGE : celle de l'état à la SORTIE.
Tu ne vois PAS l'image d'entrée — tu disposais uniquement de sa description
textuelle déjà extraite (matériau, couleur, condition, défauts), qui fait foi
pour l'état "avant". Base-toi sur cette description texte pour l'état
d'entrée, et sur l'image pour juger et localiser précisément l'état de
sortie.

ATTENTION : l'image peut montrer PLUSIEURS éléments à la fois (ex : une
photo d'extérieur de véhicule montre pare-choc + portière + jante en même
temps). Une "zone approximative connue" peut t'être fournie dans le message
utilisateur pour indiquer où se trouve CET élément précis sur l'image —
utilise-la pour ne pas confondre son état avec celui d'un élément voisin.
Si elle est fournie, ta "bbox_pct" doit rester cohérente avec cette zone
(tu peux l'affiner, pas la déplacer vers un autre objet de l'image).

Réponds STRICTEMENT avec un JSON valide, sans texte autour, sans balises
markdown. Schéma de sortie obligatoire :

{
  "status": "unchanged" | "normal_wear" | "damage" | "evolution",
  "severity": "none" | "low" | "medium" | "high",
  "confidence": float entre 0 et 1,
  "reasoning": string,
  "estimated_cost_eur": float,
  "bbox_pct": [x_min, y_min, x_max, y_max] | null
}

"bbox_pct" localise la zone de divergence sur l'image de SORTIE, en
coordonnées normalisées entre 0 et 1 (0,0 = coin haut-gauche, 1,1 = coin
bas-droit), au format [x_min, y_min, x_max, y_max]. Mets null si
status="unchanged" ou si tu ne peux pas localiser précisément l'anomalie
(ex: changement diffus sur toute la surface).

Définitions strictes des statuts :
- unchanged     : aucune différence perceptible entre entrée et sortie.
- normal_wear   : usure normale liée au temps/à l'usage (vétusté) — PAS une
                  faute imputable au locataire.
- damage        : dégradation anormale, incompatible avec un usage ou un
                  vieillissement normal sur la durée d'occupation.
- evolution     : changement neutre non imputable (déco, meuble déplacé,
                  éclairage différent...) — à ne SURTOUT PAS confondre avec
                  une dégradation.

--- EXEMPLES DE FAUX POSITIFS ("technical_noise") À NE PAS CLASSER "damage" ---

Exemple 1 — Décoloration/usure solaire diffuse :
Observation : une surface (mur, sellerie, plastique extérieur...) est
légèrement plus claire/décolorée par endroits en sortie qu'en entrée, sans
contour net.
Raisonnement attendu : décoloration progressive et diffuse sur toute une
zone exposée à la lumière ou à l'usage, cohérente avec le temps écoulé — pas
un défaut localisé.
-> status = "normal_wear", pas "damage".

Exemple 2 — Angle de photo / luminosité différents :
Observation : l'élément "semble" différent mais l'angle de prise de vue, la
distance à l'objet et la luminosité ambiante ne sont pas identiques entre
les deux photos.
Raisonnement attendu : la différence apparente s'explique par les
conditions de prise de vue, pas par l'état réel de l'élément.
-> status = "unchanged" si aucune anomalie n'est confirmée à angle comparable,
   confidence modérée (le doute doit rester visible dans le reasoning).

Exemple 3 (contre-exemple, pour calibrer) — Trou/impact net et localisé :
Observation : impact circulaire net de quelques centimètres (mur : trou de
perçage ; pare-brise : impact de gravillon net et récent), bords nets,
absent en entrée.
Raisonnement attendu : incompatible avec un vieillissement normal ; défaut
localisé et brutal, cause probable = choc ou perçage.
-> status = "damage", severity = "high".

Exemple 4 — Cas ambigu, incertitude de datation (ex : impact de gravillon sur
pare-brise) :
Observation : un petit impact (quelques mm) est visible en sortie sans
équivalent visible en entrée, MAIS rien dans les descriptions ne permet
d'exclure qu'il était déjà présent mais trop discret pour avoir été noté
à l'entrée.
Raisonnement attendu : documente le défaut, mais signale explicitement
l'incertitude sur son antériorité plutôt que de trancher à tort — c'est
plus utile pour l'utilisateur qu'un statut affirmé à tort.
-> status = "damage", severity = "low" à "medium" selon la taille,
   confidence MODÉRÉE (< 0.6), et "reasoning" doit mentionner explicitement
   que l'antériorité du défaut ne peut pas être confirmée avec certitude.

Exemple 5 — Usure d'usage normale et diffuse (ex : affaissement/décoloration
de siège conducteur) :
Observation : la sellerie du siège le plus utilisé est légèrement affaissée
et/ou décolorée par rapport à l'entrée, de façon diffuse (pas de déchirure
ni de tache localisée).
Raisonnement attendu : conforme à un usage normal et prolongé, pas à un fait
générateur ponctuel imputable à une négligence.
-> status = "normal_wear", pas "damage", même si le changement est net.

--- FIN DES EXEMPLES ---

Consignes générales :
- N'invente jamais un coût précis sans base raisonnable : donne un ordre de
  grandeur réaliste pour la réparation de CET élément, 0 si status != "damage".
- "reasoning" doit être compréhensible par un non-expert (futur lecteur du
  rapport PDF) : explique le POURQUOI du statut choisi, pas seulement le QUOI.
- En cas de doute réel entre deux statuts, choisis le moins pénalisant pour
  le locataire et baisse la confidence en conséquence — ce n'est pas à toi
  de trancher un litige, seulement de documenter objectivement.
- "bbox_pct" doit être une estimation honnête et resserrée sur l'anomalie
  elle-même (pas la moitié de l'image) : mieux vaut null qu'une zone trop
  large ou mal placée."""


def build_comparison_prompt(
    checkpoint_id: str,
    room: str,
    entry_properties: Dict[str, Any],
    exit_properties: Dict[str, Any],
    element_type: str | None = None,
    known_bbox_pct: list | None = None,
) -> str:
    """Construit le message utilisateur pour comparer une paire de nœuds.

    Une seule image est envoyée avec ce prompt (celle de sortie) via
    `image_paths=[exit_image]` au moment de l'appel LLM — voir
    agents.Agent_B.nodes.compare_node. Contrainte du VLM hébergé : 1 image
    par requête maximum.

    `known_bbox_pct`, si fourni, vient du Module A (localisation de ce
    checkpoint établie lors de l'extraction initiale) : utile quand l'image
    contient plusieurs éléments, pour que le modèle ne confonde pas ce
    checkpoint avec un voisin visible sur la même photo.
    """
    header = [f"Checkpoint : {checkpoint_id}", f"Pièce/zone : {room}"]
    if element_type:
        header.append(f"Type d'élément : {element_type}")
    if known_bbox_pct:
        header.append(
            "Zone approximative connue de CET élément sur l'image (issue de "
            f"l'extraction initiale) : {known_bbox_pct} "
            "(coordonnées normalisées [x_min, y_min, x_max, y_max])"
        )

    return (
        "L'image fournie ci-dessous est celle de la SORTIE. Elle peut contenir "
        "d'autres éléments que celui à évaluer : concentre-toi UNIQUEMENT sur "
        "le checkpoint suivant.\n"
        + "\n".join(header)
        + "\n\nDescription extraite à l'ENTRÉE (pas d'image disponible, texte uniquement) :\n"
        + json.dumps(entry_properties, indent=2, ensure_ascii=False)
        + "\n\nDescription extraite à la SORTIE (correspond à l'image fournie) :\n"
        + json.dumps(exit_properties, indent=2, ensure_ascii=False)
        + "\n\nRéponds uniquement avec le JSON demandé, rien d'autre."
    )
