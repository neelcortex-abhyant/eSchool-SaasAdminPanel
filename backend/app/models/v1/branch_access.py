"""V1 user ↔ school branch access (same UUID identity as AuthContext / v1_user_roles)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.v1.base import V1Base


class UserBranchAccess(V1Base):
    """Which branches a v1 school_admin may access.

    user_id is always v1_users.id — never legacy users.id.
    """

    __tablename__ = "v1_user_branch_access"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("v1_users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    branch_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    access_role: Mapped[str] = mapped_column(String(32), nullable=False, default="branch_admin")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
