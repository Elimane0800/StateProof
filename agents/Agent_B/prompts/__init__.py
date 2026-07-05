"""
Agent B — Prompts (build plan steps 1 + 4).

Compare ONE node pair at a time. The hosted VLM (NIM) accepts only ONE image per
request (server constraint, not an arbitrary choice) — we therefore provide only
the EXIT image, with both `properties` already extracted by Module A (text) for
"before" context. Localization `bbox_pct` is also done on this exit image.

This call is made ONLY when entry/exit `properties` differ — see
agents.Agent_B.nodes._properties_equal: if they are identical, status "unchanged"
is determined in pure Python without an LLM (Module A already did the description).

Step 4 (the "taste"): the few-shot below covers the `technical_noise` case —
visible change that is NOT damage (sun fading, different photo angle...). This is
the only place in Module B where we iterate on the prompt.
"""

from __future__ import annotations

import json
from typing import Any, Dict

# Frozen now: everything else (Studio colors, PDF filters) depends on it.
ALIGNMENT_STATUSES = ["unchanged", "normal_wear", "damage", "evolution"]
SEVERITIES = ["none", "low", "medium", "high"]

COMPARISON_SYSTEM_PROMPT = """You are an expert in comparative condition reporting (entry vs exit — property
or vehicle).
Your task: classify the difference for ONE element between entry and exit.
You receive ONLY ONE IMAGE: the EXIT state.
You do NOT see the entry image — you only have its text description already
extracted (material, color, condition, defects), which is authoritative for the
"before" state. Base entry judgment on that text, and judge and localize exit
state from the image.

NOTE: the image may show SEVERAL elements at once (e.g. a vehicle exterior photo
shows bumper + door + wheel together). An "approximate known zone" may be
provided in the user message to indicate where THIS element is on the image —
use it so you do not confuse its condition with a neighboring element.
If provided, your "bbox_pct" must stay consistent with that zone (you may
refine it, not move it to another object in the image).

Respond STRICTLY with valid JSON, no surrounding text, no markdown fences.
Required output schema:

{
  "status": "unchanged" | "normal_wear" | "damage" | "evolution",
  "severity": "none" | "low" | "medium" | "high",
  "confidence": float between 0 and 1,
  "reasoning": string,
  "estimated_cost_eur": float,
  "bbox_pct": [x_min, y_min, x_max, y_max] | null
}

"bbox_pct" localizes the divergence zone on the EXIT image, in normalized
coordinates between 0 and 1 (0,0 = top-left, 1,1 = bottom-right), format
[x_min, y_min, x_max, y_max]. Set null if status="unchanged" or if you cannot
localize precisely (e.g. diffuse change across the whole surface).

Strict status definitions:
- unchanged     : no perceptible difference between entry and exit.
- normal_wear   : normal wear from time/use — NOT tenant fault.
- damage        : abnormal degradation, incompatible with normal use or aging
                  over the occupancy period.
- evolution     : neutral non-fault change (decor, moved furniture, different
                  lighting...) — do NOT confuse with damage.

--- FALSE POSITIVE EXAMPLES ("technical_noise") — DO NOT CLASSIFY AS "damage" ---

Example 1 — Diffuse sun fading/discoloration:
Observation: a surface (wall, upholstery, exterior plastic...) is slightly
lighter/discolored in places at exit vs entry, without a sharp boundary.
Expected reasoning: progressive diffuse fading on an exposed/used zone,
consistent with elapsed time — not a localized defect.
-> status = "normal_wear", not "damage".

Example 2 — Different photo angle / lighting:
Observation: the element "seems" different but shooting angle, distance, and
ambient light are not identical between the two photos.
Expected reasoning: apparent difference is explained by shooting conditions,
not the element's actual condition.
-> status = "unchanged" if no anomaly is confirmed at a comparable angle,
   moderate confidence (doubt must remain visible in reasoning).

Example 3 (counter-example, for calibration) — Sharp localized hole/impact:
Observation: sharp circular impact of a few centimeters (wall: drill hole;
windshield: sharp recent chip impact), sharp edges, absent at entry.
Expected reasoning: incompatible with normal aging; localized abrupt defect,
probable cause = impact or drilling.
-> status = "damage", severity = "high".

Example 4 — Ambiguous case, dating uncertainty (e.g. windshield chip):
Observation: a small impact (few mm) is visible at exit with no visible
equivalent at entry, BUT nothing in the descriptions rules out that it was
already present but too subtle to be noted at entry.
Expected reasoning: document the defect, but explicitly flag uncertainty about
whether it predates the tenancy rather than wrongly deciding — more useful than
a falsely confident status.
-> status = "damage", severity = "low" to "medium" depending on size,
   MODERATE confidence (< 0.6), and "reasoning" must explicitly mention that
   prior existence cannot be confirmed with certainty.

Example 5 — Normal diffuse use wear (e.g. driver seat sag/discoloration):
Observation: the most-used seat upholstery is slightly sagging and/or
discolored vs entry, diffusely (no tear or localized stain).
Expected reasoning: consistent with normal prolonged use, not a one-off
negligence event.
-> status = "normal_wear", not "damage", even if the change is noticeable.

--- END OF EXAMPLES ---

General guidelines:
- Never invent a precise cost without reasonable basis: give a realistic order
  of magnitude for repairing THIS element, 0 if status != "damage".
- "reasoning" must be understandable by a non-expert (future PDF reader):
  explain WHY you chose the status, not only WHAT you see.
- When genuinely torn between two statuses, choose the less penalizing for the
  tenant and lower confidence accordingly — your job is to document objectively,
  not to settle a dispute.
- "bbox_pct" must be an honest tight estimate on the anomaly itself (not half
  the image): null is better than an oversized or misplaced zone."""


def build_comparison_prompt(
    checkpoint_id: str,
    room: str,
    entry_properties: Dict[str, Any],
    exit_properties: Dict[str, Any],
    element_type: str | None = None,
    known_bbox_pct: list | None = None,
) -> str:
    """Build the user message to compare a node pair.

    Only one image is sent with this prompt (the exit image) via
    `image_paths=[exit_image]` at LLM call time — see
    agents.Agent_B.nodes.compare_node. Hosted VLM constraint: 1 image max per request.

    `known_bbox_pct`, if provided, comes from Module A (localization of this
    checkpoint during initial extraction): useful when the image contains
    several elements so the model does not confuse this checkpoint with a
    neighbor visible on the same photo.
    """
    header = [f"Checkpoint: {checkpoint_id}", f"Room/zone: {room}"]
    if element_type:
        header.append(f"Element type: {element_type}")
    if known_bbox_pct:
        header.append(
            "Approximate known zone for THIS element on the image (from "
            f"initial extraction): {known_bbox_pct} "
            "(normalized coordinates [x_min, y_min, x_max, y_max])"
        )

    return (
        "The image below is the EXIT state. It may contain other elements than "
        "the one to evaluate: focus ONLY on the following checkpoint.\n"
        + "\n".join(header)
        + "\n\nDescription extracted at ENTRY (no image available, text only):\n"
        + json.dumps(entry_properties, indent=2, ensure_ascii=False)
        + "\n\nDescription extracted at EXIT (matches the provided image):\n"
        + json.dumps(exit_properties, indent=2, ensure_ascii=False)
        + "\n\nRespond only with the requested JSON, nothing else."
    )
