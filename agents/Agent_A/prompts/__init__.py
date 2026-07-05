"""
Agent A — Prompts (build plan step 2).

Two modes, two prompts:
- "One checkpoint per image" mode (`build_state_description_prompt`): one image
  + one checkpoint_id. Easiest brick to validate in isolation.
- "Multiple checkpoints per image" mode (`build_multi_checkpoint_prompt`):
  a single photo may show SEVERAL elements to inspect (e.g. a vehicle exterior
  photo shows bumper + door + wheel + windshield at once). The VLM must identify
  EACH requested element, describe its condition AND localize it (`bbox_pct`) so
  Module B knows where to look without confusing two neighboring checkpoints.
"""

from __future__ import annotations

import json
from typing import List, Optional

STATE_DESCRIPTION_SYSTEM_PROMPT = """You are an expert in property condition reporting.
Your task: objectively describe the condition of ONE element visible in a photo
(a wall, floor, electrical outlet...), for an initial or final condition report.

Respond STRICTLY with valid JSON, no surrounding text, no markdown fences,
no comments. Required output schema:

{
  "material": string | null,
  "color": string | null,
  "condition": "intact" | "usé" | "endommagé" | "unknown",
  "defects": string[],
  "confidence": float between 0 and 1
}

Guidelines:
- Base your answer ONLY on what you actually observe in the provided image.
- If the requested element is hidden, blurry, out of frame, or absent, set
  "condition": "unknown" and a low "confidence" (< 0.3).
- "defects" lists visible anomalies (crack, stain, hole, burn mark,
  water ring, chip...). Empty list if no visible anomaly.
- "confidence" reflects your certainty about the full description, not
  condition alone.
- Never invent unobservable details (e.g. do not guess a material hidden by furniture)."""


def build_state_description_prompt(
    checkpoint_id: str,
    element_type: str | None = None,
    room: str | None = None,
) -> str:
    """Build the user message for a checkpoint image."""
    hints = []
    if room:
        hints.append(f"Room: {room}")
    if element_type:
        hints.append(f"Expected element type: {element_type}")
    hints.append(f"Checkpoint id: {checkpoint_id}")

    return (
        "Describe the condition of the element visible in this image, limited to "
        "the element identified below.\n"
        + "\n".join(hints)
        + "\n\nRespond only with the requested JSON, nothing else."
    )


# ---------------------------------------------------------------------------
# Multi-checkpoint mode: one image, several elements to describe + localize
# ---------------------------------------------------------------------------

MULTI_CHECKPOINT_SYSTEM_PROMPT = """You are an expert in condition reporting (property or vehicle).
Your task: on ONE photo showing SEVERAL distinct elements, objectively describe
the condition of EACH requested element, and LOCALIZE each one in the image.

Respond STRICTLY with valid JSON, no surrounding text, no markdown fences,
no comments. Required output schema: a JSON object whose keys are EXACTLY the
provided checkpoint ids, each value following this schema:

{
  "<checkpoint_id>": {
    "visible": bool,
    "material": string | null,
    "color": string | null,
    "condition": "intact" | "usé" | "endommagé" | "unknown",
    "defects": string[],
    "confidence": float between 0 and 1,
    "bbox_pct": [x_min, y_min, x_max, y_max] | null
  },
  ...
}

Guidelines:
- Treat EACH requested checkpoint independently, but use global image context to
  tell them apart (e.g. do not confuse right front fender with right front door).
- "visible" = false if the requested element does not appear at all in this
  photo (out of frame, hidden); in that case set "condition": "unknown",
  "confidence": 0.0, "bbox_pct": null, "defects": [].
- "bbox_pct" localizes the element in normalized coordinates between 0 and 1
  (0,0 = top-left, 1,1 = bottom-right), format [x_min, y_min, x_max, y_max].
  It must target the TIGHTEST zone that actually contains the element (not the
  whole photo). Set null only when "visible" is false.
- "defects" lists visible anomalies on THIS element (scratch, dent, crack, stain,
  impact, wear...). Empty list if no visible anomaly.
- Never invent unobservable details. Base your answer only on what you see.
- Respond for ALL requested checkpoints, even those not visible."""


def build_multi_checkpoint_prompt(
    checkpoints: List["CheckpointDef"],  # noqa: F821 - avoid circular import; see common.schemas
    room: Optional[str] = None,
) -> str:
    """Build the user message listing all checkpoints expected on this image
    (one photo = potentially several elements)."""
    items = []
    for cp in checkpoints:
        cp_id = cp.id if hasattr(cp, "id") else cp
        cp_type = getattr(cp, "element_type", None)
        items.append({"checkpoint_id": cp_id, "type_attendu": cp_type})

    header = f"Photographed zone: {room}\n" if room else ""
    return (
        header
        + "Here is the list of elements to identify, describe, and localize in "
        "this image:\n"
        + json.dumps(items, indent=2, ensure_ascii=False)
        + "\n\nRespond only with the requested JSON object (one key per "
        "checkpoint_id above), nothing else."
    )
