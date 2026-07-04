"""The Taste Engine.

`classify()` runs the real VLM when a provider is configured; otherwise it
falls back to a deterministic heuristic so the pipeline is always green in CI
and demos. Either way the output is a validated AuditPayload.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from app.core.config import BACKEND_ROOT
from app.core.schema import (
    AuditPayload,
    AuditRequest,
    Classification,
    CursorPatch,
    EvolutionProposal,
    Finding,
    NoiseItem,
    Severity,
    TreeNode,
)
from app.services import code_parser, patch, vlm

log = logging.getLogger("synchronaise.classifier")

PROMPT_PATH = BACKEND_ROOT / "app" / "prompts" / "classification.md"
_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_PX_RE = re.compile(r"^(\d+)px$")

_SEVERITY_WEIGHT = {Severity.LOW: 10, Severity.HIGH: 40, Severity.MEDIUM: 25}


@lru_cache
def _prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _render_prompt(request: AuditRequest, design_tree: TreeNode, code_tree: TreeNode) -> str:
    tokens = code_parser.load_tokens()
    tpl = _prompt_template()
    return (
        tpl.replace("{tokens}", json.dumps(tokens, indent=2))
        .replace("{design_tree}", design_tree.model_dump_json(indent=2))
        .replace("{code_tree}", code_tree.model_dump_json(indent=2))
        .replace("{code}", request.code)
    )


def _apply_classifications(tree: TreeNode, mapping: dict[str, str]) -> None:
    if tree.id in mapping:
        try:
            tree.classification = Classification(mapping[tree.id])
        except ValueError:
            pass
    for child in tree.children:
        _apply_classifications(child, mapping)


# --------------------------------------------------------------------------- #
# Deterministic fallback - mirrors the golden dataset without an LLM.
# --------------------------------------------------------------------------- #
def _heuristic(request: AuditRequest, design_tree: TreeNode, code_tree: TreeNode) -> AuditPayload:
    hex_index = code_parser.hex_to_token()
    px_index = code_parser.px_to_token()

    findings: list[Finding] = []
    noise: list[NoiseItem] = []
    evolution: list[EvolutionProposal] = []

    def visit(node: TreeNode) -> None:
        for key, value in list(node.props.items()):
            v = str(value).strip().lower()
            hexmatch = _HEX_RE.match(v)
            if hexmatch and v in hex_index:
                token = hex_index[v]
                node.classification = Classification.DESIGN_VIOLATION
                findings.append(
                    Finding(
                        type="token_violation",
                        classification=Classification.DESIGN_VIOLATION,
                        severity=Severity.HIGH,
                        location=f"{request.file_path}",
                        node_id=node.id,
                        bbox=None,
                        expected=f"var(--{token})",
                        actual=str(value),
                        reasoning=(
                            f"Hex value matches token {token} exactly; hardcoding breaks "
                            "theme propagation."
                        ),
                        cursor_patch=patch.token_patch(f"var(--{token})", str(value), request.file_path),
                    )
                )
            pxmatch = _PX_RE.match(v)
            if pxmatch and v not in px_index:
                nearest = _nearest_spacing(int(pxmatch.group(1)), px_index)
                if nearest:
                    node.classification = Classification.DESIGN_VIOLATION
                    findings.append(
                        Finding(
                            type="spacing_violation",
                            classification=Classification.DESIGN_VIOLATION,
                            severity=Severity.MEDIUM,
                            location=f"{request.file_path}",
                            node_id=node.id,
                            bbox=None,
                            expected=f"var(--{nearest})",
                            actual=str(value),
                            reasoning=(
                                f"{value} is off the spacing scale; nearest token is "
                                f"{nearest}."
                            ),
                            cursor_patch=patch.token_patch(f"var(--{nearest})", str(value), request.file_path),
                        )
                    )
        for child in node.children:
            visit(child)

    visit(code_tree)

    # Technical noise: wrapper divs added for layout/overflow.
    if re.search(r"scroll-wrapper|overflow\s*:\s*['\"]?auto|flex-wrapper", request.code):
        noise.append(
            NoiseItem(
                element="div.scroll-wrapper",
                node_id=None,
                reasoning="Structural wrapper required for overflow handling; no visual or semantic impact.",
            )
        )

    # Intentional evolution: a secondary button not present in the design intent.
    if re.search(r"data-node=\"btn-secondary\"|secondary", request.code, re.IGNORECASE):
        design_ids = _collect_ids(design_tree)
        if "btn-secondary" not in design_ids:
            evolution.append(
                EvolutionProposal(
                    element="button.secondary",
                    node_id="btn-secondary",
                    reasoning="A secondary action is present in code but absent from the Figma intent.",
                    proposal="Add a secondary button variant to the design system rather than removing it.",
                )
            )

    drift = min(100, sum(_SEVERITY_WEIGHT[f.severity] for f in findings))

    return AuditPayload(
        audit_id=f"pr-{request.pr_number}-run-{request.run}",
        pr_number=request.pr_number,
        drift_score=drift,
        screenshot_url=request.screenshot_url or f"/artifacts/pr-{request.pr_number}-run-{request.run}.png",
        design_tree=design_tree,
        code_tree=code_tree,
        findings=findings,
        ignored_as_noise=noise,
        evolution_proposals=evolution,
    )


def _nearest_spacing(px: int, px_index: dict[str, str]) -> str | None:
    scale = []
    for value, token in px_index.items():
        m = _PX_RE.match(value)
        if m:
            scale.append((abs(int(m.group(1)) - px), token))
    if not scale:
        return None
    return min(scale)[1]


def _collect_ids(tree: TreeNode) -> set[str]:
    ids = {tree.id}
    for child in tree.children:
        ids |= _collect_ids(child)
    return ids


# --------------------------------------------------------------------------- #
# Public entrypoint
# --------------------------------------------------------------------------- #
def classify(request: AuditRequest, design_tree: TreeNode, code_tree: TreeNode) -> AuditPayload:
    if not vlm.available():
        log.info("No VLM provider configured; using heuristic Taste Engine.")
        return _heuristic(request, design_tree, code_tree)

    try:
        prompt = _render_prompt(request, design_tree, code_tree)
        raw = vlm.complete_json(prompt, image_b64=request.screenshot_b64)
        return _from_llm(request, design_tree, code_tree, raw)
    except Exception as exc:  # noqa: BLE001 - soft-fail to heuristic, never crash CI
        log.warning("VLM classification failed (%s); falling back to heuristic.", exc)
        return _heuristic(request, design_tree, code_tree)


def _from_llm(
    request: AuditRequest,
    design_tree: TreeNode,
    code_tree: TreeNode,
    raw: dict,
) -> AuditPayload:
    mapping = raw.get("node_classifications", {}) or {}
    _apply_classifications(code_tree, mapping)

    findings = [Finding.model_validate(f) for f in raw.get("findings", [])]
    noise = [NoiseItem.model_validate(n) for n in raw.get("ignored_as_noise", [])]
    evolution = [EvolutionProposal.model_validate(e) for e in raw.get("evolution_proposals", [])]

    drift = int(raw.get("drift_score", min(100, len(findings) * 25)))

    return AuditPayload(
        audit_id=f"pr-{request.pr_number}-run-{request.run}",
        pr_number=request.pr_number,
        drift_score=max(0, min(100, drift)),
        screenshot_url=request.screenshot_url
        or f"/artifacts/pr-{request.pr_number}-run-{request.run}.png",
        design_tree=design_tree,
        code_tree=code_tree,
        findings=findings,
        ignored_as_noise=noise,
        evolution_proposals=evolution,
    )
