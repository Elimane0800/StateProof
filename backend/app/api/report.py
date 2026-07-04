"""GET /report/{audit_id} - pure read of a stored audit for the Studio."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.core.schema import AuditPayload
from app.services import storage

router = APIRouter(tags=["report"])


def _mock() -> AuditPayload:
    data = json.loads(get_settings().mock_path.read_text(encoding="utf-8"))
    return AuditPayload.model_validate(data)


@router.get("/report/{audit_id}", response_model=AuditPayload)
def get_report(audit_id: str) -> AuditPayload:
    payload = storage.load(audit_id)
    if payload is None:
        # In mock mode, any id resolves to the seeded demo audit so the Studio
        # is never a blank screen during development.
        if get_settings().mock_mode:
            return _mock()
        raise HTTPException(status_code=404, detail=f"No audit stored for '{audit_id}'.")
    return payload


@router.get("/reports")
def list_reports() -> dict[str, list[str]]:
    return {"audit_ids": storage.list_ids()}
