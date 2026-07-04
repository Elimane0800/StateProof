"""SQLModel engine + CRUD helpers for the rental registry.

One engine, created lazily from `settings.database_url`. Postgres (psycopg v3)
in Docker, or a zero-setup local SQLite file otherwise - the API code is
identical either way. `storage.py` (JSON audit payloads) is untouched; this is
the SQL side for users + rentals.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Optional

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import get_settings
from app.core.registry import Rental, RentalStatus, User


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    url = settings.database_url
    # SQLite needs the same connection usable across FastAPI's threadpool.
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    if url.startswith("sqlite"):
        # Ensure the parent dir exists for a file-based SQLite DB.
        settings.data_dir.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, echo=False, connect_args=connect_args)


def init_db() -> None:
    """Create tables if they do not exist. Safe to call on every startup."""
    SQLModel.metadata.create_all(get_engine())


def session() -> Session:
    return Session(get_engine())


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
def create_user(email: str, name: Optional[str] = None) -> User:
    with session() as db:
        user = User(email=email, name=name)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def get_user(user_id: str) -> Optional[User]:
    with session() as db:
        return db.get(User, user_id)


def get_user_by_email(email: str) -> Optional[User]:
    with session() as db:
        return db.exec(select(User).where(User.email == email)).first()


# --------------------------------------------------------------------------- #
# Rentals
# --------------------------------------------------------------------------- #
def create_rental(
    user_id: str, plate: Optional[str] = None, started_at: Optional[datetime] = None
) -> Rental:
    with session() as db:
        rental = Rental(user_id=user_id, plate=plate)
        if started_at is not None:
            rental.started_at = started_at
        db.add(rental)
        db.commit()
        db.refresh(rental)
        return rental


def get_rental(rental_id: str) -> Optional[Rental]:
    with session() as db:
        return db.get(Rental, rental_id)


def list_rentals(user_id: Optional[str] = None) -> list[Rental]:
    with session() as db:
        stmt = select(Rental).order_by(Rental.created_at)
        if user_id is not None:
            stmt = stmt.where(Rental.user_id == user_id)
        return list(db.exec(stmt).all())


def set_video(rental_id: str, *, which: str, path: str) -> Optional[Rental]:
    """Set video_in_path or video_out_path. `which` is 'in' or 'out'."""
    if which not in {"in", "out"}:
        raise ValueError("which must be 'in' or 'out'")
    with session() as db:
        rental = db.get(Rental, rental_id)
        if rental is None:
            return None
        if which == "in":
            rental.video_in_path = path
        else:
            rental.video_out_path = path
        db.add(rental)
        db.commit()
        db.refresh(rental)
        return rental


def close_rental(rental_id: str, ended_at: Optional[datetime] = None) -> Optional[Rental]:
    with session() as db:
        rental = db.get(Rental, rental_id)
        if rental is None:
            return None
        rental.status = RentalStatus.CLOSED
        rental.ended_at = ended_at or datetime.utcnow()
        db.add(rental)
        db.commit()
        db.refresh(rental)
        return rental
