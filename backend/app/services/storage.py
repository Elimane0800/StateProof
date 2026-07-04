"""Persist and retrieve audits by audit_id.

Deliberately simple: one JSON file per audit under DATA_DIR. Good enough for a
hackathon and trivially inspectable. Swap for SQLite/Redis later without
touching the API layer.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from app.core.config import get_settings
from app.core.schema import AuditPayload

_lock = threading.Lock()


def _dir() -> Path:
    d = get_settings().data_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(audit_id: str) -> Path:
    safe = audit_id.replace("/", "_").replace("..", "_")
    return _dir() / f"{safe}.json"


def save(payload: AuditPayload) -> None:
    path = _path(payload.audit_id)
    # Write to a temp file (not matched by the *.json glob) then atomically
    # replace, so a concurrent reader never observes a partially-written file.
    tmp = path.with_name(path.name + ".tmp")
    with _lock:
        tmp.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, path)


def load(audit_id: str) -> AuditPayload | None:
    path = _path(audit_id)
    with _lock:
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
    return AuditPayload.model_validate(json.loads(raw))


def list_ids() -> list[str]:
    return sorted(p.stem for p in _dir().glob("*.json"))


def _registry_dir() -> Path:
    d = get_settings().data_dir.parent / "registry"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _registry_path(plate: str) -> Path:
    safe = plate.replace("/", "_").replace("..", "_").upper()
    return _registry_dir() / f"{safe}.json"


def register_plate_audit(plate: str, audit_id: str) -> None:
    """Append audit_id to the plate-keyed in-memory registry file."""
    path = _registry_path(plate)
    with _lock:
        data: dict = {"plate": plate.upper(), "audit_ids": []}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        ids: list[str] = data.setdefault("audit_ids", [])
        if audit_id not in ids:
            ids.append(audit_id)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def audits_for_plate(plate: str) -> list[str]:
    path = _registry_path(plate)
    with _lock:
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("audit_ids", []))
