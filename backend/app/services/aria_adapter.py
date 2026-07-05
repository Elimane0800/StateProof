"""Live return inspection via the ARIA agent pipeline (Modules A -> B -> D).

Bridges StateProof's ``POST /inspection/return`` to the ARIA vehicle pipeline:
decode the uploaded pickup/return frames, run Module A (build a condition graph
per state), Module B (align the two graphs + confidence), Module D (legal
qualification of every ``damage`` edge), then map the result onto the frozen
``AuditPayload`` contract the Studio renders.

Live-only: Modules A and B call the VLM, so ``NVIDIA_API_KEY`` is required.
There is no mock fallback here by design.
"""

from __future__ import annotations

import base64
import logging
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

from app.core.config import REPO_ROOT, get_settings
from app.core.schema import (
    AuditPayload,
    Classification,
    EvolutionProposal,
    Finding,
    NoiseItem,
    Severity,
    TreeNode,
)
from app.services import display_en, patch

log = logging.getLogger("stateproof.aria")

# Make the repo-root ``agents`` package importable when uvicorn runs from
# ``backend/`` locally (in the container PYTHONPATH already covers this).
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# Per-part indicative cost, mirrored from the Studio (ExplanationPanel
# SEVERITY_COST) so the total and the per-part figures reconcile.
_SEVERITY_COST: dict[Severity, int] = {
    Severity.LOW: 45,
    Severity.MEDIUM: 120,
    Severity.HIGH: 280,
}

# ARIA AlignmentStatus -> StateProof Classification.
_STATUS_TO_CLASSIFICATION: dict[str, Classification] = {
    "unchanged": Classification.ALIGNED,
    "normal_wear": Classification.TECHNICAL_NOISE,
    "damage": Classification.DESIGN_VIOLATION,
    "evolution": Classification.INTENTIONAL_EVOLUTION,
}


def _status_str(edge: Any) -> str:
    return edge.status.value if hasattr(edge.status, "value") else str(edge.status)


def _severity(raw: Any) -> Severity:
    value = raw.value if hasattr(raw, "value") else str(raw)
    if value == "high":
        return Severity.HIGH
    if value == "medium":
        return Severity.MEDIUM
    # ARIA's "low" and "none" both fall into the lowest chargeable band.
    return Severity.LOW


def _label(checkpoint_id: str) -> str:
    return display_en.checkpoint_label(checkpoint_id)


def _write_frame(b64: str, audit_id: str, suffix: str) -> Path:
    """Persist a base64 frame under the artifacts dir; return its path."""
    settings = get_settings()
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    raw = base64.b64decode(b64.split(",", 1)[-1])
    path = settings.artifacts_dir / f"{audit_id}-{suffix}.png"
    path.write_bytes(raw)
    return path


def _artifact_url(path: Path) -> str:
    return f"/artifacts/{path.name}"


def _condition_str(node: Any) -> str:
    if node is None:
        return "unknown"
    props = node.properties
    return display_en.condition_summary(props.condition, props.defects or None)


def _node_to_tree(node: Any, classification: Classification) -> TreeNode:
    props: dict[str, Any] = {
        "condition": display_en.condition_label(node.properties.condition),
    }
    if node.properties.material:
        props["material"] = node.properties.material
    if node.properties.color:
        props["color"] = node.properties.color
    if node.properties.defects:
        props["defects"] = [display_en.defect_label(d) for d in node.properties.defects]
    return TreeNode(
        id=node.id,
        label=_label(node.checkpoint_id),
        type=display_en.element_type_label(node.element_type),
        classification=classification,
        props=props,
    )


def _build_tree(
    graph: Any, plate: str, classification_by_node: dict[str, Classification]
) -> TreeNode:
    children = [
        _node_to_tree(
            graph.nodes[node_id],
            classification_by_node.get(node_id, Classification.ALIGNED),
        )
        for node_id in sorted(graph.nodes.keys())
    ]
    return TreeNode(
        id="vehicle",
        label=f"Vehicle {plate}",
        type="vehicle",
        classification=Classification.ALIGNED,
        props={"plate": plate},
        children=children,
    )


def _to_audit_payload(
    *,
    plate: str,
    audit_id: str,
    entry_graph: Any,
    exit_graph: Any,
    edges: list,
    legal_by_node: dict[str, Any],
    pickup_url: str,
    return_url: str,
) -> AuditPayload:
    classification_by_node: dict[str, Classification] = {}
    findings: list[Finding] = []
    noise: list[NoiseItem] = []
    evolution: list[EvolutionProposal] = []
    total_eur = 0

    for edge in edges:
        status = _status_str(edge)
        classification_by_node[edge.node_id] = _STATUS_TO_CLASSIFICATION.get(
            status, Classification.ALIGNED
        )
        entry_node = entry_graph.get_node(edge.node_id)
        exit_node = exit_graph.get_node(edge.node_id)
        label = _label(edge.checkpoint_id)

        if status == "damage":
            severity = _severity(edge.severity)
            cost = _SEVERITY_COST[severity]
            total_eur += cost
            reasoning = edge.reasoning or ""
            legal = legal_by_node.get(edge.node_id)
            if legal and legal.reasoning:
                reasoning = (
                    f"{reasoning}\n\nLegal qualification: "
                    f"{display_en.legal_reasoning_en(legal.reasoning)}"
                )
            expected = _condition_str(entry_node)
            actual = _condition_str(exit_node)
            findings.append(
                Finding(
                    type="damage",
                    classification=Classification.DESIGN_VIOLATION,
                    severity=severity,
                    location=display_en.room_label(edge.room),
                    node_id=edge.node_id,
                    bbox=edge.bbox_pct,
                    expected=expected,
                    actual=actual,
                    reasoning=reasoning,
                    cursor_patch=patch.charge_notice(
                        node_id=label,
                        expected=expected,
                        actual=actual,
                        cost=cost,
                        location=display_en.room_label(edge.room),
                    ),
                )
            )
        elif status == "normal_wear":
            noise.append(
                NoiseItem(
                    element=label,
                    node_id=edge.node_id,
                    reasoning=edge.reasoning
                    or "Acceptable surface wear vs the registered baseline.",
                )
            )
        elif status == "evolution":
            evolution.append(
                EvolutionProposal(
                    element=label,
                    node_id=edge.node_id,
                    reasoning=edge.reasoning
                    or "Change recorded against the pickup baseline.",
                    proposal="Recorded change vs pickup baseline - not chargeable.",
                )
            )

    design_tree = _build_tree(entry_graph, plate, {})
    code_tree = _build_tree(exit_graph, plate, classification_by_node)

    return AuditPayload(
        audit_id=audit_id,
        pr_number=0,
        asset_id=plate,
        drift_score=total_eur,
        pickup_screenshot_url=pickup_url,
        screenshot_url=return_url,
        design_tree=design_tree,
        code_tree=code_tree,
        findings=findings,
        ignored_as_noise=noise,
        evolution_proposals=evolution,
    )


def run_live_inspection(
    plate: str,
    pickup_b64: Optional[str],
    return_b64: Optional[str],
    audit_id: Optional[str] = None,
) -> AuditPayload:
    """Run the ARIA vehicle pipeline on the pickup/return frames for ``plate``."""
    settings = get_settings()
    if not settings.nvidia_api_key:
        raise RuntimeError(
            "NVIDIA_API_KEY is required for live inspection (live-only mode)."
        )
    if not pickup_b64 or not return_b64:
        raise ValueError("Both a pickup and a return image are required.")

    # Imported lazily so the module (and the rest of the app) still imports
    # even when the agents package or its heavy deps are unavailable.
    from agents.Agent_A.graph import build_graph_from_zone_images
    from agents.Agent_B.graph import align
    from agents.Agent_D.graph import qualify
    from agents.common.schemas import PropertyConfig

    audit_id = audit_id or f"return-{uuid.uuid4().hex[:8]}"
    pickup_path = _write_frame(pickup_b64, audit_id, "pickup")
    return_path = _write_frame(return_b64, audit_id, "return")

    config = PropertyConfig.from_json_file(str(settings.checkpoints_path))

    log.info("ARIA Module A: building pickup/return graphs for %s", plate)
    entry_graph = build_graph_from_zone_images(config, {"exterieur": str(pickup_path)})
    exit_graph = build_graph_from_zone_images(config, {"exterieur": str(return_path)})

    log.info("ARIA Module B: aligning %d checkpoints", len(entry_graph.nodes))
    edges = align(entry_graph, exit_graph)

    legal_by_node: dict[str, Any] = {}
    for edge in edges:
        if _status_str(edge) != "damage":
            continue
        entry_node = entry_graph.get_node(edge.node_id)
        exit_node = exit_graph.get_node(edge.node_id)
        reference = entry_node or exit_node
        legal_by_node[edge.node_id] = qualify(
            edge,
            settings.occupancy_months,
            element_category=reference.element_type if reference else None,
            grid=None,
            entry_node=entry_node,
            exit_node=exit_node,
        )

    return _to_audit_payload(
        plate=plate,
        audit_id=audit_id,
        entry_graph=entry_graph,
        exit_graph=exit_graph,
        edges=edges,
        legal_by_node=legal_by_node,
        pickup_url=_artifact_url(pickup_path),
        return_url=_artifact_url(return_path),
    )
