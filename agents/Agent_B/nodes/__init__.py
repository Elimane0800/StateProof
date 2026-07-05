"""
Agent B — Nodes (build plan step 2).

compare_node(entry_node, exit_node) -> AlignmentEdge:
  - deterministic short-circuit (_properties_equal, zero LLM) if Module A
    extracted identical `properties` at entry/exit: no need to call a model to
    confirm an obvious "unchanged".
  - otherwise, calls the comparison prompt (agents.Agent_B.prompts) on one
    pair, with ONE image only (exit — hosted VLM limits requests to 1 image),
    validates/parses against `AlignmentEdge`.
  - retries once, then fallback marked `comparison_failed=True` (never raises —
    consistent with Module A robustness).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import ValidationError

from agents.base_model.base_llm_nim import BaseLLMProvider, DEFAULT_VISION_MODEL
from agents.common.schemas import AlignmentEdge, Node
from agents.Agent_B.prompts import COMPARISON_SYSTEM_PROMPT, build_comparison_prompt

MAX_RETRIES = 1


def _clean_bbox_pct(raw_bbox) -> Optional[List[float]]:
    """Validate `bbox_pct` without ever raising: a malformed zone degrades to
    `None` (no watermark) rather than failing the whole comparison."""
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
    """True if both Module A extractions are identical in substance (condition +
    defects) — confidence is ignored; two extractions may legitimately differ in
    confidence without the actual state having changed."""
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
    """Compare the same checkpoint between `entry_node` and `exit_node`.

    Assumes `entry_node.id == exit_node.id` (same checkpoint, same config) —
    see agents.Agent_B.graph.align for the loop that guarantees this.
    """
    # Deterministic short-circuit: Module A already said everything; no LLM needed
    # to confirm an identical checkpoint is "unchanged".
    if _properties_equal(entry_node.properties, exit_node.properties):
        return AlignmentEdge(
            node_id=entry_node.id,
            checkpoint_id=entry_node.checkpoint_id,
            room=entry_node.room,
            status="unchanged",
            severity="none",
            confidence=min(entry_node.properties.confidence, exit_node.properties.confidence),
            reasoning=(
                "No difference between descriptions extracted by Module A at "
                "entry and exit (same condition, same defects) — "
                "deterministic qualification, no LLM call."
            ),
            estimated_cost_eur=0.0,
            comparison_failed=False,
        )

    llm = llm or _make_llm()

    # Module A localization hint (known zone for THIS checkpoint in the shared
    # image) — prefer exit bbox (the image actually sent to the VLM), fall back
    # to entry if absent.
    known_bbox_pct = exit_node.bbox_pct or entry_node.bbox_pct

    base_prompt = build_comparison_prompt(
        checkpoint_id=entry_node.checkpoint_id,
        room=entry_node.room,
        entry_properties=entry_node.properties.model_dump(),
        exit_properties=exit_node.properties.model_dump(),
        element_type=entry_node.element_type,
        known_bbox_pct=known_bbox_pct,
    )

    # Hosted VLM accepts only 1 image per request: send exit (also where bbox_pct
    # is localized), fall back to entry if only that is available.
    image_path = exit_node.image_path or entry_node.image_path
    image_paths = [image_path] if image_path else []

    last_error: Optional[str] = None
    for attempt in range(MAX_RETRIES + 1):
        user_message = base_prompt
        if attempt > 0 and last_error:
            user_message += (
                f"\n\nWARNING: your previous response was invalid "
                f"({last_error}). Fix it and return ONLY the expected JSON."
            )

        raw = llm.invoke_for_json(user_message, image_paths=image_paths)
        if raw is None:
            last_error = "response not parseable as JSON"
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

    # Fallback: never crash align() for one failed pair.
    # `comparison_failed` lets Module C show "data not available" rather than
    # a false status.
    return AlignmentEdge(
        node_id=entry_node.id,
        checkpoint_id=entry_node.checkpoint_id,
        room=entry_node.room,
        status="unchanged",
        severity="none",
        confidence=0.0,
        reasoning="Automatic comparison unavailable — manual review required.",
        estimated_cost_eur=0.0,
        comparison_failed=True,
    )
