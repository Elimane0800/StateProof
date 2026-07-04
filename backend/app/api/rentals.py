"""Rental registry endpoints - the Backend API track's surface.

Flow: create a user, create a renting, upload the pickup video, later upload the
return video, read the renting back with resolvable video URLs. Videos are
streamed to disk under UPLOADS_DIR/{rental_id}/{in|out}/; the AI track reads
those paths and sets `audit_id` after diffing the pair.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import get_settings
from app.core.registry import Rental, RentalCreate, RentalRead, User, UserCreate
from app.services import registry_store

router = APIRouter(tags=["rentals"])

_CHUNK = 1024 * 1024  # 1 MiB streaming chunks


def _to_read(rental: Rental) -> RentalRead:
    """Attach resolvable /uploads URLs to a stored rental."""

    def url(rel: Optional[str]) -> Optional[str]:
        return f"/uploads/{rel}" if rel else None

    return RentalRead(
        id=rental.id,
        user_id=rental.user_id,
        plate=rental.plate,
        status=rental.status,
        started_at=rental.started_at,
        ended_at=rental.ended_at,
        video_in_path=rental.video_in_path,
        video_out_path=rental.video_out_path,
        video_in_url=url(rental.video_in_path),
        video_out_url=url(rental.video_out_path),
        audit_id=rental.audit_id,
        created_at=rental.created_at,
    )


def _save_upload(rental_id: str, which: str, file: UploadFile) -> str:
    """Stream an upload to disk, enforcing extension + size limits.

    Returns the path relative to UPLOADS_DIR (posix), which is what we store in
    the DB and what maps directly onto the /uploads static mount.
    """
    settings = get_settings()
    ext = Path(file.filename or "").suffix.lower()
    if ext not in settings.allowed_video_ext:
        allowed = ", ".join(sorted(settings.allowed_video_ext))
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported video type '{ext or 'unknown'}'. Allowed: {allowed}.",
        )

    rel = f"{rental_id}/{which}/{uuid.uuid4()}{ext}"
    dest = settings.uploads_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)

    max_bytes = settings.max_upload_mb * 1024 * 1024
    written = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = file.file.read(_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    out.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Video exceeds the {settings.max_upload_mb} MB limit.",
                    )
                out.write(chunk)
    finally:
        file.file.close()

    return rel


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
@router.post("/users", response_model=User)
def create_user(body: UserCreate) -> User:
    if registry_store.get_user_by_email(body.email) is not None:
        raise HTTPException(status_code=409, detail=f"User '{body.email}' already exists.")
    return registry_store.create_user(email=body.email, name=body.name)


@router.get("/users/{user_id}/rentals", response_model=list[RentalRead])
def list_user_rentals(user_id: str) -> list[RentalRead]:
    if registry_store.get_user(user_id) is None:
        raise HTTPException(status_code=404, detail=f"No user '{user_id}'.")
    return [_to_read(r) for r in registry_store.list_rentals(user_id=user_id)]


# --------------------------------------------------------------------------- #
# Rentals
# --------------------------------------------------------------------------- #
@router.post("/rentals", response_model=RentalRead)
def create_rental(body: RentalCreate) -> RentalRead:
    if registry_store.get_user(body.user_id) is None:
        raise HTTPException(status_code=404, detail=f"No user '{body.user_id}'.")
    rental = registry_store.create_rental(
        user_id=body.user_id, plate=body.plate, started_at=body.started_at
    )
    return _to_read(rental)


@router.get("/rentals", response_model=list[RentalRead])
def list_rentals() -> list[RentalRead]:
    return [_to_read(r) for r in registry_store.list_rentals()]


@router.get("/rentals/{rental_id}", response_model=RentalRead)
def get_rental(rental_id: str) -> RentalRead:
    rental = registry_store.get_rental(rental_id)
    if rental is None:
        raise HTTPException(status_code=404, detail=f"No rental '{rental_id}'.")
    return _to_read(rental)


@router.post("/rentals/{rental_id}/video-in", response_model=RentalRead)
def upload_video_in(rental_id: str, file: UploadFile = File(...)) -> RentalRead:
    return _upload(rental_id, "in", file)


@router.post("/rentals/{rental_id}/video-out", response_model=RentalRead)
def upload_video_out(rental_id: str, file: UploadFile = File(...)) -> RentalRead:
    return _upload(rental_id, "out", file)


def _upload(rental_id: str, which: str, file: UploadFile) -> RentalRead:
    if registry_store.get_rental(rental_id) is None:
        raise HTTPException(status_code=404, detail=f"No rental '{rental_id}'.")
    rel = _save_upload(rental_id, which, file)
    rental = registry_store.set_video(rental_id, which=which, path=rel)
    if rental is None:  # deleted between the checks - unlikely
        raise HTTPException(status_code=404, detail=f"No rental '{rental_id}'.")
    return _to_read(rental)
