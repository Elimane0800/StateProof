"""Rental registry tables - the API track's persistence model.

Deliberately kept separate from the AI-owned classification models in
`schema.py`. Two tables only:

  * User   - the person who rents.
  * Rental - one renting event, holding the two video paths (pickup / return)
             as separate columns. Charging is decided by diffing a renting's own
             `video_in` vs `video_out`, so no cross-rental history is modelled.

`audit_id` is a plain nullable string, not a foreign key: the AI track links its
stored audit payload here once it has processed the pair, without this module
having to know the audit's shape.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RentalStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=_uuid, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class Rental(SQLModel, table=True):
    __tablename__ = "rentals"

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    plate: Optional[str] = Field(default=None, index=True)
    status: RentalStatus = Field(default=RentalStatus.ACTIVE)
    started_at: datetime = Field(default_factory=_now)
    ended_at: Optional[datetime] = None
    # Two separate columns, one path each - filled as the videos are uploaded.
    video_in_path: Optional[str] = None
    video_out_path: Optional[str] = None
    # Set by the AI track after it diffs the pair. Not a FK on purpose.
    audit_id: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


# --------------------------------------------------------------------------- #
# API request/response DTOs (not tables).
# --------------------------------------------------------------------------- #
class UserCreate(SQLModel):
    email: str
    name: Optional[str] = None


class RentalCreate(SQLModel):
    user_id: str
    plate: Optional[str] = None
    started_at: Optional[datetime] = None


class RentalRead(SQLModel):
    """A rental plus resolvable video URLs for the Studio."""

    id: str
    user_id: str
    plate: Optional[str]
    status: RentalStatus
    started_at: datetime
    ended_at: Optional[datetime]
    video_in_path: Optional[str]
    video_out_path: Optional[str]
    video_in_url: Optional[str] = None
    video_out_url: Optional[str] = None
    audit_id: Optional[str]
    created_at: datetime
