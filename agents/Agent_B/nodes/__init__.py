"""
Agent B — Nodes (Étape 2 du plan de construction).

compare_node(entry_node, exit_node) -> AlignmentEdge :
  - court-circuit déterministe (_properties_equal, zéro LLM) si les
    `properties` extraites par le Module A sont identiques entrée/sortie :
    inutile de rappeler un modèle pour confirmer un "unchanged" évident.
  - sinon, appelle le prompt de comparaison (agents.Agent_B.prompts) sur une
    seule paire, avec UNE SEULE image (celle de sortie — le VLM hébergé
    limite les requêtes à 1 image), valide/parse la réponse contre
    `AlignmentEdge`.
  - retry une fois, puis fallback marqué `comparison_failed=True` (jamais
    d'exception qui remonte — cohérent avec la robustesse du Module A).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import ValidationError

from agents.base_model.base_llm_nim import BaseLLMProvider, DEFAULT_VISION_MODEL
from agents.common.schemas import AlignmentEdge, Node
from agents.Agent_B.prompts import COMPARISON_SYSTEM_PROMPT, build_comparison_prompt

MAX_RETRIES = 1


def _clean_bbox_pct(raw_bbox) -> Optional[List[float]]:
    """Valide `bbox_pct` sans jamais lever d'exception : une zone mal formée
    dégrade juste en `None` (pas de watermark) plutôt que de faire échouer
    toute la comparaison."""
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        return None
    try:
        values = [float(v) for v in raw_bbox]
    except (TypeError, ValueError):
        return None
    if not all(0.0 <= v <= 1.0 for v in values):
        return None
    x_min, y_min, x_max, y_max = values
    if x_max <= x_min or y_max <= y_min:
        return None
    return values


def _properties_equal(entry_props, exit_props) -> bool:
    """True si les deux descriptions extraites par le Module A sont
    identiques sur le fond (condition + défauts) — la confidence n'entre
    pas en compte, deux extractions peuvent légitimement différer en
    confiance sans que l'état réel ait changé."""
    if entry_props.condition != exit_props.condition:
        return False
    return set(entry_props.defects) == set(exit_props.defects)


def _make_llm() -> BaseLLMProvider:
    return BaseLLMProvider(
        system_prompt=COMPARISON_SYSTEM_PROMPT,
        model_name=DEFAULT_VISION_MODEL,
        temperature=0.2,
    )


def compare_node(
    entry_node: Node,
    exit_node: Node,
    llm: Optional[BaseLLMProvider] = None,
) -> AlignmentEdge:
    """Compare un même checkpoint entre `entry_node` et `exit_node`.

    Suppose `entry_node.id == exit_node.id` (même checkpoint, même config) —
    voir agents.Agent_B.graph.align pour la boucle qui garantit cette invariance.
    """
    # Court-circuit déterministe : Module A a déjà tout dit, pas besoin d'un
    # LLM pour confirmer qu'un checkpoint identique est "unchanged".
    if _properties_equal(entry_node.properties, exit_node.properties):
        return AlignmentEdge(
            node_id=entry_node.id,
            checkpoint_id=entry_node.checkpoint_id,
            room=entry_node.room,
            status="unchanged",
            severity="none",
            confidence=min(entry_node.properties.confidence, exit_node.properties.confidence),
            reasoning=(
                "Aucune différence entre les descriptions extraites par le Module A "
                "à l'entrée et à la sortie (même condition, mêmes défauts) — "
                "qualification déterministe, sans appel LLM."
            ),
            estimated_cost_eur=0.0,
            comparison_failed=False,
        )

    llm = llm or _make_llm()

    # Indice de localisation du Module A (zone connue de CE checkpoint dans
    # l'image partagée) — priorité au bbox de l'image de sortie (celle
    # effectivement envoyée au VLM), repli sur celui d'entrée si absent.
    known_bbox_pct = exit_node.bbox_pct or entry_node.bbox_pct

    base_prompt = build_comparison_prompt(
        checkpoint_id=entry_node.checkpoint_id,
        room=entry_node.room,
        entry_properties=entry_node.properties.model_dump(),
        exit_properties=exit_node.properties.model_dump(),
        element_type=entry_node.element_type,
        known_bbox_pct=known_bbox_pct,
    )

    # Le VLM hébergé n'accepte qu'1 image par requête : on envoie celle de
    # sortie (c'est aussi sur elle que se fait la localisation bbox_pct),
    # avec repli sur l'entrée si jamais seule celle-ci est disponible.
    image_path = exit_node.image_path or entry_node.image_path
    image_paths = [image_path] if image_path else []

    last_error: Optional[str] = None
    for attempt in range(MAX_RETRIES + 1):
        user_message = base_prompt
        if attempt > 0 and last_error:
            user_message += (
                f"\n\nATTENTION : ta réponse précédente était invalide "
                f"({last_error}). Corrige et renvoie UNIQUEMENT le JSON attendu."
            )

        raw = llm.invoke_for_json(user_message, image_paths=image_paths)
        if raw is None:
            last_error = "réponse non parsable en JSON"
            continue

        try:
            return AlignmentEdge(
                node_id=entry_node.id,
                checkpoint_id=entry_node.checkpoint_id,
                room=entry_node.room,
                status=raw["status"],
                severity=raw.get("severity", "none"),
                confidence=raw.get("confidence", 0.0),
                reasoning=raw.get("reasoning", ""),
                estimated_cost_eur=raw.get("estimated_cost_eur", 0.0),
                comparison_failed=False,
                bbox_pct=_clean_bbox_pct(raw.get("bbox_pct")),
            )
        except (ValidationError, KeyError) as e:
            last_error = str(e)
            continue

    # Fallback : ne jamais faire planter align() pour une paire ratée.
    # Le flag `comparison_failed` permet au Module C d'afficher
    # "donnée non disponible" plutôt qu'un faux statut.
    return AlignmentEdge(
        node_id=entry_node.id,
        checkpoint_id=entry_node.checkpoint_id,
        room=entry_node.room,
        status="unchanged",
        severity="none",
        confidence=0.0,
        reasoning="Comparaison automatique indisponible — vérification manuelle requise.",
        estimated_cost_eur=0.0,
        comparison_failed=True,
    )
