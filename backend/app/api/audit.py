"""POST /audit - the core endpoint the GitHub Action calls.

Orchestration lives here and is intentionally thin:
  1. tree_builder assembles design_tree (Figma intent) + code_tree (code AST).
  2. classifier (the Taste Engine) triages every drift node.
  3. the frozen payload is assembled, stored by audit_id and returned.

In mock mode it returns the seeded demo payload so R4 and R5 are unblocked
from hour one.
"""

from __future__ import annotations

import json

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.schema import AuditPayload, AuditRequest
from app.services import classifier, storage, tree_builder

router = APIRouter(tags=["audit"])


def _mock_for(request: AuditRequest) -> AuditPayload:
    data = json.loads(get_settings().mock_path.read_text(encoding="utf-8"))
    payload = AuditPayload.model_validate(data)
    payload.pr_number = request.pr_number
    payload.audit_id = f"pr-{request.pr_number}-run-{request.run}"
    return payload


@router.post("/audit", response_model=AuditPayload)
def create_audit(request: AuditRequest) -> AuditPayload:
    settings = get_settings()

    if settings.mock_mode:
        payload = _mock_for(request)
        storage.save(payload)
        return payload

    design_tree, code_tree = tree_builder.build_trees(request)
    payload = classifier.classify(request, design_tree=design_tree, code_tree=code_tree)
    storage.save(payload)
    return payload
