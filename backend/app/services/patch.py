"""Cursor patch generation.

Two paths:
  - token_patch(): deterministic patch for a detected token/spacing violation.
  - generate_fix(): the Studio prompt box - node context + NL request -> patch,
    using the VLM when available, else a template.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from app.core.schema import AuditPayload, CursorPatch, TreeNode
from app.services import vlm

log = logging.getLogger("synchronaise.patch")


def token_patch(expected: str, actual: str, location: str) -> CursorPatch:
    return CursorPatch(
        prompt=(
            f"In {location}, replace the hardcoded value {actual} with {expected} "
            "from our design tokens."
        ),
        diff=f"- {actual}\n+ {expected}",
    )


def _find_node(node: TreeNode, node_id: str) -> Optional[TreeNode]:
    if node.id == node_id:
        return node
    for child in node.children:
        found = _find_node(child, node_id)
        if found:
            return found
    return None


def generate_fix(
    audit: Optional[AuditPayload], node_id: str, user_prompt: str
) -> Optional[CursorPatch]:
    node = _find_node(audit.code_tree, node_id) if audit else None
    node_json = node.model_dump_json(indent=2) if node else "{}"

    if vlm.available():
        try:
            prompt = (
                "You are SynchronAIse. Given a component node and a natural-language "
                "change request, produce a Cursor patch. Return ONLY JSON: "
                '{"prompt": "...", "diff": "- old\\n+ new"}.\n\n'
                f"Node:\n{node_json}\n\nRequest: {user_prompt}"
            )
            raw = vlm.complete_json(prompt)
            return CursorPatch.model_validate(raw)
        except Exception as exc:  # noqa: BLE001
            log.warning("VLM fix failed (%s); using template patch.", exc)

    # Template fallback: still paste-ready in Cursor.
    return CursorPatch(
        prompt=f"On node '{node_id}': {user_prompt}. Use our design tokens, not hardcoded values.",
        diff=f"// apply to node '{node_id}':\n// {user_prompt}",
    )
