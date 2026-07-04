"""Parse a React/TSX component into a code_tree of TreeNodes.

This is a pragmatic, dependency-free JSX scanner - not a full TypeScript AST.
It is tuned for the hero StatusCard: it walks JSX tags, honours explicit
`data-node="<id>"` markers for stable node ids (shared with the design_tree),
and extracts inline `style={{ ... }}` declarations so the classifier can reason
about hardcoded values vs tokens.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import BACKEND_ROOT
from app.core.schema import Classification, TreeNode

TOKENS_PATH = BACKEND_ROOT / "app" / "data" / "tokens.json"

_TAG_RE = re.compile(r"<(/?)([A-Za-z][\w.]*)((?:[^<>]|\"[^\"]*\"|'[^']*'|\{[^{}]*\})*?)(/?)>")
_STYLE_RE = re.compile(r"style=\{\{(.*?)\}\}", re.DOTALL)
_DATA_NODE_RE = re.compile(r"data-node=\"([^\"]+)\"")
_PROP_RE = re.compile(r"([A-Za-z0-9_-]+)\s*:\s*(\"[^\"]*\"|'[^']*'|`[^`]*`|[^,]+)")

_TYPE_BY_TAG = {
    "button": "button",
    "svg": "icon",
    "img": "icon",
    "h1": "text",
    "h2": "text",
    "h3": "text",
    "p": "text",
    "span": "text",
}


@lru_cache
def load_tokens() -> dict[str, Any]:
    return json.loads(TOKENS_PATH.read_text(encoding="utf-8"))


@lru_cache
def hex_to_token() -> dict[str, str]:
    tokens = load_tokens()
    return {v.lower(): k for k, v in tokens.get("colors", {}).items()}


@lru_cache
def px_to_token() -> dict[str, str]:
    out: dict[str, str] = {}
    for group in ("spacing", "radius"):
        for name, value in load_tokens().get(group, {}).items():
            out[str(value)] = name
    return out


def _clean_value(raw: str) -> str:
    return raw.strip().strip("\"'`").strip()


def _extract_style(attr_blob: str) -> dict[str, str]:
    match = _STYLE_RE.search(attr_blob)
    if not match:
        return {}
    body = match.group(1)
    props: dict[str, str] = {}
    for name, value in _PROP_RE.findall(body):
        props[name.strip()] = _clean_value(value)
    return props


def _derive_node_id(tag: str, attr_blob: str, seen: dict[str, int]) -> str:
    explicit = _DATA_NODE_RE.search(attr_blob)
    if explicit:
        return explicit.group(1)
    base = _TYPE_BY_TAG.get(tag.lower(), tag.lower())
    seen[base] = seen.get(base, 0) + 1
    return base if seen[base] == 1 else f"{base}-{seen[base]}"


def parse_component(code: str, root_id: str = "card", root_label: str = "StatusCard") -> TreeNode:
    """Build a code_tree from component source.

    Every node starts `aligned`; the classifier is responsible for reclassifying
    based on the Taste Engine. Parser only supplies structure + observed props.
    """
    root = TreeNode(id=root_id, label=root_label, type="container", props={})
    stack: list[TreeNode] = [root]
    seen: dict[str, int] = {}
    root_assigned = False

    for closing, tag, attr_blob, self_closing in _TAG_RE.findall(code):
        if tag[0].isupper() and tag not in {"StatusCard"}:
            # Custom component tag - treat as container element.
            pass

        if closing:
            if len(stack) > 1:
                stack.pop()
            continue

        style = _extract_style(attr_blob)
        node_id = _derive_node_id(tag, attr_blob, seen)

        if not root_assigned and tag.lower() in {"div", "section", "article", "statuscard"}:
            # First container becomes the root; fold its style in.
            root.props.update(style)
            root_assigned = True
            if self_closing:
                continue
            continue

        node = TreeNode(
            id=node_id,
            label=node_id.replace("-", " ").title(),
            type=_TYPE_BY_TAG.get(tag.lower(), "container"),
            classification=Classification.ALIGNED,
            props=style,
        )
        stack[-1].children.append(node)
        if not self_closing:
            stack.append(node)

    return root
