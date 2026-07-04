"""
Agent A — Nodes (Étape 3 + Étape 5 du plan de construction).

build_node(image, checkpoint_id) -> Node :
  - appelle le prompt de description d'état (agents.Agent_A.prompts)
  - parse la réponse et la valide contre le schéma pydantic `NodeProperties`
  - retry une fois avec l'erreur en contexte si le JSON est invalide
  - fallback sur un Node "unknown"/confidence=0 plutôt que de planter le
    pipeline pour un seul checkpoint raté (Étape 5 — robustesse).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import ValidationError

from agents.base_model.base_llm_nim import BaseLLMProvider, DEFAULT_VISION_MODEL
from agents.common.schemas import CheckpointDef, Node, NodeProperties
from agents.Agent_A.prompts import (
    MULTI_CHECKPOINT_SYSTEM_PROMPT,
    STATE_DESCRIPTION_SYSTEM_PROMPT,
    build_multi_checkpoint_prompt,
    build_state_description_prompt,
)

MAX_RETRIES = 1


def _make_llm() -> BaseLLMProvider:
    return BaseLLMProvider(
        system_prompt=STATE_DESCRIPTION_SYSTEM_PROMPT,
        model_name=DEFAULT_VISION_MODEL,
        temperature=0.2,
    )


def _make_multi_llm() -> BaseLLMProvider:
    return BaseLLMProvider(
        system_prompt=MULTI_CHECKPOINT_SYSTEM_PROMPT,
        model_name=DEFAULT_VISION_MODEL,
        temperature=0.2,
    )


def build_node(
    image_path: str,
    checkpoint_id: str,
    room: str,
    element_type: Optional[str] = None,
    llm: Optional[BaseLLMProvider] = None,
) -> Node:
    """Décrit un checkpoint à partir d'une image et retourne un `Node` validé.

    Ne lève jamais d'exception : en cas d'échec définitif du parsing/validation,
    retourne un Node dégradé (`extraction_failed=True`, condition="unknown",
    confidence=0.0) pour que `build_graph` puisse continuer sur les autres
    checkpoints.
    """
    llm = llm or _make_llm()
    node_id = f"{room}:{checkpoint_id}"
    base_prompt = build_state_description_prompt(checkpoint_id, element_type, room)

    last_error: Optional[str] = None
    for attempt in range(MAX_RETRIES + 1):
        user_message = base_prompt
        if attempt > 0 and last_error:
            user_message += (
                f"\n\nATTENTION : ta réponse précédente était invalide "
                f"({last_error}). Corrige et renvoie UNIQUEMENT le JSON attendu."
            )

        raw = llm.invoke_for_json(user_message, image_paths=[image_path])
        if raw is None:
            last_error = "réponse non parsable en JSON"
            continue

        try:
            properties = NodeProperties.model_validate(raw)
        except ValidationError as e:
            last_error = str(e)
            continue

        return Node(
            id=node_id,
            checkpoint_id=checkpoint_id,
            room=room,
            element_type=element_type,
            image_path=image_path,
            properties=properties,
            extraction_failed=False,
        )

    # Étape 5 — fallback : un checkpoint raté ne doit jamais faire planter tout le pipeline.
    return Node(
        id=node_id,
        checkpoint_id=checkpoint_id,
        room=room,
        element_type=element_type,
        image_path=image_path,
        properties=NodeProperties(condition="unknown", confidence=0.0),
        extraction_failed=True,
    )


def _clean_bbox_pct(raw_bbox) -> Optional[List[float]]:
    """Même validation que côté Module B — une zone mal formée dégrade en
    `None` plutôt que de faire échouer l'extraction du checkpoint."""
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


def build_nodes_from_image(
    image_path: str,
    checkpoints: List[CheckpointDef],
    room: str,
    llm: Optional[BaseLLMProvider] = None,
) -> List[Node]:
    """Décrit PLUSIEURS checkpoints à partir d'UNE SEULE image (mode
    multi-entités, ex : une photo d'extérieur de véhicule montrant pare-choc
    + portière + jante + pare-brise en même temps).

    Un seul appel VLM pour toute l'image (au lieu d'un appel par checkpoint) :
    le modèle reçoit la liste des checkpoints attendus et doit répondre pour
    chacun, avec sa propre `bbox_pct` de localisation dans l'image partagée.

    Ne lève jamais d'exception : si l'appel global échoue ou si un
    checkpoint précis manque/est mal formé dans la réponse, ce checkpoint
    individuel dégrade en `Node` "unknown" (`extraction_failed=True`) sans
    affecter les autres checkpoints de la même image.
    """
    llm = llm or _make_multi_llm()
    base_prompt = build_multi_checkpoint_prompt(checkpoints, room)

    raw: Optional[dict] = None
    last_error: Optional[str] = None
    for attempt in range(MAX_RETRIES + 1):
        user_message = base_prompt
        if attempt > 0 and last_error:
            user_message += (
                f"\n\nATTENTION : ta réponse précédente était invalide "
                f"({last_error}). Corrige et renvoie UNIQUEMENT le JSON attendu, "
                "avec une clé par checkpoint_id demandé."
            )

        response = llm.invoke_for_json(user_message, image_paths=[image_path])
        if response is None or not isinstance(response, dict):
            last_error = "réponse non parsable en JSON (objet attendu)"
            continue
        raw = response
        break

    nodes: List[Node] = []
    for checkpoint in checkpoints:
        node_id = f"{room}:{checkpoint.id}"
        entry = raw.get(checkpoint.id) if raw else None

        if not isinstance(entry, dict):
            nodes.append(Node(
                id=node_id,
                checkpoint_id=checkpoint.id,
                room=room,
                element_type=checkpoint.element_type,
                image_path=image_path,
                visible=False,
                properties=NodeProperties(condition="unknown", confidence=0.0),
                extraction_failed=True,
            ))
            continue

        try:
            properties = NodeProperties.model_validate({
                "material": entry.get("material"),
                "color": entry.get("color"),
                "condition": entry.get("condition", "unknown"),
                "defects": entry.get("defects", []),
                "confidence": entry.get("confidence", 0.0),
            })
            nodes.append(Node(
                id=node_id,
                checkpoint_id=checkpoint.id,
                room=room,
                element_type=checkpoint.element_type,
                image_path=image_path,
                bbox_pct=_clean_bbox_pct(entry.get("bbox_pct")),
                visible=bool(entry.get("visible", True)),
                properties=properties,
                extraction_failed=False,
            ))
        except ValidationError:
            nodes.append(Node(
                id=node_id,
                checkpoint_id=checkpoint.id,
                room=room,
                element_type=checkpoint.element_type,
                image_path=image_path,
                visible=False,
                properties=NodeProperties(condition="unknown", confidence=0.0),
                extraction_failed=True,
            ))

    return nodes
