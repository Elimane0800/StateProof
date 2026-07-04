"""Load ground-truth fixtures from demo/ground-truth/ for MOCK_MODE (B-P4).

Falls back to backend/mocks/audit_mock.json when demo files are absent so
integration branches stay green before feat/demo merges.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.config import get_settings
from app.core.schema import AuditPayload

_PLATE_SAFE = re.compile(r"[^A-Za-z0-9-]+")


def normalize_plate(plate: str) -> str:
    return _PLATE_SAFE.sub("", plate.strip().upper())


def _normalize_plate(plate: str) -> str:
    return normalize_plate(plate)


def _ground_truth_dir() -> Path:
    return get_settings().ground_truth_dir


def registry_path(plate: str) -> Path:
    safe = _normalize_plate(plate)
    return _ground_truth_dir() / "registry" / f"{safe}.json"


def load_registry(plate: str) -> dict | None:
    path = registry_path(plate)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_baseline(plate: str | None = None) -> dict | None:
    plate = _normalize_plate(plate or get_settings().default_plate)
    gt = _ground_truth_dir()
    reg = load_registry(plate)
    if reg and reg.get("baseline_file"):
        path = gt / str(reg["baseline_file"])
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    fallback = gt / "pickup-baseline.json"
    if fallback.exists():
        return json.loads(fallback.read_text(encoding="utf-8"))
    return None


def load_return_audit(plate: str | None = None) -> AuditPayload | None:
    plate = _normalize_plate(plate or get_settings().default_plate)
    gt = _ground_truth_dir()
    reg = load_registry(plate)
    if reg and reg.get("return_audit_file"):
        path = gt / str(reg["return_audit_file"])
        if path.exists():
            return AuditPayload.model_validate(json.loads(path.read_text(encoding="utf-8")))
    fallback = gt / "return-audit.json"
    if fallback.exists():
        return AuditPayload.model_validate(json.loads(fallback.read_text(encoding="utf-8")))
    return None


def load_mock_file() -> AuditPayload:
    path = get_settings().mock_path
    data = json.loads(path.read_text(encoding="utf-8"))
    return AuditPayload.model_validate(data)


def resolve_mock_payload(plate: str | None = None) -> AuditPayload:
    """Plate-keyed registry lookup, then ground-truth file, then frozen mock."""
    plate = _normalize_plate(plate or get_settings().default_plate)
    loaded = load_return_audit(plate)
    if loaded is not None:
        return loaded
    return load_mock_file()


def detected_component_ids(payload: AuditPayload) -> list[str]:
    ids: list[str] = []
    for finding in payload.findings:
        if finding.node_id:
            ids.append(finding.node_id)
    for noise in payload.ignored_as_noise:
        if noise.node_id:
            ids.append(noise.node_id)
    for proposal in payload.evolution_proposals:
        if proposal.node_id:
            ids.append(proposal.node_id)
    return ids
