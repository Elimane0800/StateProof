"""
Agent A — Nodes (build plan steps 3 + 5).

build_node(image, checkpoint_id) -> Node:
  - calls the state-description prompt (agents.Agent_A.prompts)
  - parses and validates the response against pydantic `NodeProperties`
  - retries once with the error in context if JSON is invalid
  - falls back to an "unknown"/confidence=0 Node rather than crashing the
    pipeline for one failed checkpoint (step 5 — robustness).
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
    """Describe a checkpoint from an image and return a validated `Node`.

    Never raises: on definitive parse/validation failure, returns a degraded
    Node (`extraction_failed=True`, condition="unknown", confidence=0.0) so
    `build_graph` can continue on other checkpoints.
    """
    llm = llm or _make_llm()
    node_id = f"{room}:{checkpoint_id}"
    base_prompt = build_state_description_prompt(checkpoint_id, element_type, room)

    last_error: Optional[str] = None
    for attempt in range(MAX_RETRIES + 1):
        user_message = base_prompt
        if attempt > 0 and last_error:
            user_message += (
                f"\n\nWARNING: your previous response was invalid "
                f"({last_error}). Fix it and return ONLY the expected JSON."
            )

        raw = llm.invoke_for_json(user_message, image_paths=[image_path])
        if raw is None:
            last_error = "response not parseable as JSON"
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

    # Step 5 — fallback: one failed checkpoint must never crash the whole pipeline.
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
    """Same validation as Module B — a malformed zone degrades to `None`
    rather than failing checkpoint extraction."""
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
    """Describe SEVERAL checkpoints from ONE image (multi-entity mode, e.g. a
    vehicle exterior photo showing bumper + door + wheel + windshield together).

    One VLM call for the entire image (instead of one per checkpoint): the model
    receives the list of expected checkpoints and must respond for each with its
    own `bbox_pct` localization in the shared image.

    Never raises: if the global call fails or a specific checkpoint is
    missing/malformed in the response, that checkpoint degrades to an "unknown"
    `Node` (`extraction_failed=True`) without affecting other checkpoints on
    the same image.
    """
    llm = llm or _make_multi_llm()
    base_prompt = build_multi_checkpoint_prompt(checkpoints, room)

    raw: Optional[dict] = None
    last_error: Optional[str] = None
    for attempt in range(MAX_RETRIES + 1):
        user_message = base_prompt
        if attempt > 0 and last_error:
            user_message += (
                f"\n\nWARNING: your previous response was invalid "
                f"({last_error}). Fix it and return ONLY the expected JSON, "
                "with one key per requested checkpoint_id."
            )

        response = llm.invoke_for_json(user_message, image_paths=[image_path])
        if response is None or not isinstance(response, dict):
            last_error = "response not parseable as JSON (object expected)"
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
