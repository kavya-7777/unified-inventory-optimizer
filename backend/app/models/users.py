"""
Database Models.
Covers: Users (login + roles), the activity log and the data-import history.
"""
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow

ROLES = ("admin", "planner", "viewer")


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True)   # stored lower-case
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="viewer")  # admin | planner | viewer
    is_active: Mapped[bool] = mapped_column(default=True)
    last_login_at: Mapped[Optional[datetime]]
    created_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow, onupdate=utcnow)


class AuditEvent(Base):
    """Who did what: pipeline runs, policy edits, alert resolutions, imports, user changes."""
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_email: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(60))      # e.g. pipeline.run, policy.update
    entity_type: Mapped[Optional[str]] = mapped_column(String(60))
    entity_id: Mapped[Optional[str]] = mapped_column(String(255))
    details: Mapped[Optional[Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        Index("ix_audit_events_created_at", "created_at"),
    )


class DataImport(Base):
    """One committed Excel/CSV upload."""
    __tablename__ = "data_imports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(255))
    user_email: Mapped[str] = mapped_column(String(255))
    summary: Mapped[Optional[Any]] = mapped_column(JSON)  # per-sheet created/updated counts
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        Index("ix_data_imports_created_at", "created_at"),
    )
