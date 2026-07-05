"""StateProof return inspection — photo → plate → registry → audit."""

from __future__ import annotations

import base64
import uuid

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.core.schema import AuditPayload, ReturnInspectionRequest
from app.services import demo_loader, storage

router = APIRouter(tags=["inspection"])


def _hero_node_id(payload: AuditPayload) -> str | None:
    for noise in payload.ignored_as_noise:
        if noise.node_id == "door_fl":
            return noise.node_id
    for noise in payload.ignored_as_noise:
        if "registry" in noise.reasoning.lower():
            return noise.node_id
    return payload.findings[0].node_id if payload.findings else None


@router.post("/inspection/return", response_model=AuditPayload)
def return_inspection(request: ReturnInspectionRequest) -> AuditPayload:
    """Run a return inspection for a license plate (MOCK_MODE uses demo ground-truth)."""
    settings = get_settings()
    plate = request.asset_id.strip()

    if settings.mock_mode:
        payload = demo_loader.resolve_mock_payload(plate)
        payload.asset_id = demo_loader.normalize_plate(plate)
        payload.audit_id = request.audit_id or payload.audit_id or f"return-{uuid.uuid4().hex[:8]}"

        def _persist(b64: str, suffix: str) -> str:
            """Save an uploaded base64 frame under artifacts and return its URL."""
            raw = base64.b64decode(b64.split(",", 1)[-1])
            settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
            art = settings.artifacts_dir / f"{payload.audit_id}-{suffix}.png"
            art.write_bytes(raw)
            return f"/artifacts/{art.name}"

        if request.screenshot_url:
            payload.screenshot_url = request.screenshot_url
        elif request.screenshot_b64:
            payload.screenshot_url = _persist(request.screenshot_b64, "return")

        if request.pickup_screenshot_url:
            payload.pickup_screenshot_url = request.pickup_screenshot_url
        elif request.pickup_b64:
            payload.pickup_screenshot_url = _persist(request.pickup_b64, "pickup")
        storage.save(payload)
        storage.register_plate_audit(plate, payload.audit_id)
        return payload

    raise HTTPException(
        status_code=501,
        detail="Live VLM return inspection requires feat/backend-api parsers; use MOCK_MODE=1.",
    )


@router.get("/registry/{plate}")
def get_registry(plate: str) -> dict:
    """Plate-keyed ledger: baseline summary + stored audit ids."""
    normalized = demo_loader.normalize_plate(plate)
    baseline = demo_loader.load_baseline(normalized)
    audit_ids = storage.audits_for_plate(normalized)
    reg = demo_loader.load_registry(normalized)
    return {
        "plate": normalized,
        "baseline": baseline,
        "audit_ids": audit_ids,
        "hero_node_id": reg.get("hero_node_id") if reg else _hero_node_id(demo_loader.resolve_mock_payload(normalized)),
    }
