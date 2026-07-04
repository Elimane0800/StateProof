"""POST /fix - the Studio prompt box.

Takes a node + a natural-language request, returns a Cursor patch. Never
commits; the developer applies it in Cursor.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.schema import FixRequest, FixResponse
from app.services import patch, storage

router = APIRouter(tags=["fix"])


@router.post("/fix", response_model=FixResponse)
def create_fix(request: FixRequest) -> FixResponse:
    audit = storage.load(request.audit_id)
    cursor_patch = patch.generate_fix(
        audit=audit,
        node_id=request.node_id,
        user_prompt=request.prompt,
    )
    if cursor_patch is None:
        raise HTTPException(status_code=422, detail="Could not generate a patch for this request.")
    return FixResponse(node_id=request.node_id, cursor_patch=cursor_patch)
