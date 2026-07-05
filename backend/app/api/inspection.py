"""StateProof return inspection — photo -> plate -> ARIA pipeline -> audit.

Live-only: the ARIA agent pipeline (Modules A -> B -> D) runs on every request
and requires ``NVIDIA_API_KEY``. There is no mock path here by design.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.core.schema import AuditPayload, ReturnInspectionRequest
from app.services import aria_adapter, demo_loader, storage

router = APIRouter(tags=["inspection"])
log = logging.getLogger("stateproof.inspection")


def _hero_node_id(payload: AuditPayload) -> str | None:
    for noise in payload.ignored_as_noise:
        if "registry" in noise.reasoning.lower():
            return noise.node_id
    return payload.findings[0].node_id if payload.findings else None


@router.post("/inspection/return", response_model=AuditPayload)
def return_inspection(request: ReturnInspectionRequest) -> AuditPayload:
    """Run a live return inspection for a plate via the ARIA agent pipeline."""
    plate = demo_loader.normalize_plate(request.asset_id)

    try:
        payload = aria_adapter.run_live_inspection(
            plate=plate,
            pickup_b64=request.pickup_b64,
            return_b64=request.screenshot_b64,
            audit_id=request.audit_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface pipeline/config failures as 500
        log.exception("Live inspection failed for plate %s", plate)
        raise HTTPException(status_code=500, detail=f"Live inspection failed: {exc}") from exc

    # Explicit URLs (e.g. already-hosted media) override the persisted frames.
    if request.screenshot_url:
        payload.screenshot_url = request.screenshot_url
    if request.pickup_screenshot_url:
        payload.pickup_screenshot_url = request.pickup_screenshot_url

    storage.save(payload)
    storage.register_plate_audit(plate, payload.audit_id)
    return payload


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
        "hero_node_id": reg.get("hero_node_id") if reg else None,
    }
