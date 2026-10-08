from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

if TYPE_CHECKING:
    from app.models.v1.session import AuthSession

from app.models.v1.base import V1Base
from app.models.v1.roles import ROLE_USER

# Active/inactive for school_admin (and future roles). 1=active, 0=inactive.
STATUS_ACTIVE = 1
STATUS_INACTIVE = 0


class User(V1Base):
    """V1 auth user — table `v1_users` (never merge with legacy integer `users`)."""

    __tablename__ = "v1_users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    mobile: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # Platform role for /api/v1 only. Signup always ROLE_USER; never client-selectable.
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=ROLE_USER, server_default=ROLE_USER, index=True)
    # Set for school_admin; null for super_admin / plain user.
    # No SQLAlchemy ForeignKey here: schools lives on legacy Base metadata; Alembic 0005
    # still creates the real FK constraint on Neon.
    school_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=STATUS_ACTIVE, server_default="1", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
