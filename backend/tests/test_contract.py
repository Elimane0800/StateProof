"""The frozen contract must never drift. Validate mocks + model against schema."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

from app.core.config import BACKEND_ROOT, REPO_ROOT
from app.core.schema import AuditPayload

SCHEMA = json.loads((REPO_ROOT / "packages" / "contract" / "schema.json").read_text("utf-8"))

PAYLOADS = [
    REPO_ROOT / "packages" / "contract" / "contract.example.json",
    BACKEND_ROOT / "mocks" / "audit_mock.json",
    REPO_ROOT / "frontend" / "src" / "mocks" / "audit.json",
]


def test_all_mocks_match_schema() -> None:
    validator = Draft7Validator(SCHEMA)
    for path in PAYLOADS:
        data = json.loads(Path(path).read_text("utf-8"))
        errors = list(validator.iter_errors(data))
        assert not errors, f"{path.name}: {[e.message for e in errors]}"


def test_mock_loads_into_pydantic_model() -> None:
    data = json.loads((BACKEND_ROOT / "mocks" / "audit_mock.json").read_text("utf-8"))
    payload = AuditPayload.model_validate(data)
    assert payload.audit_id
    assert payload.findings, "demo mock should carry at least one finding"


def test_backend_and_frontend_mocks_are_identical() -> None:
    a = json.loads((BACKEND_ROOT / "mocks" / "audit_mock.json").read_text("utf-8"))
    b = json.loads((REPO_ROOT / "frontend" / "src" / "mocks" / "audit.json").read_text("utf-8"))
    assert a == b, "backend and frontend mocks must stay in lockstep"
