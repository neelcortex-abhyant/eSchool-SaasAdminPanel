"""Gap closure: notification retry/idempotency, leave decision audit.

Revision ID: 20261030_0045
Revises: 20261030_0044
Create Date: 2026-10-30

Do not apply to Neon without explicit approval.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261030_0045"
down_revision: Union[str, None] = "20261030_0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "notifications",
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "notifications",
        sa.Column("idempotency_key", sa.String(length=191), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "uq_notifications_school_idempotency",
        "notifications",
        ["school_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL AND deleted_at IS NULL"),
    )

    op.add_column(
        "leaves",
        sa.Column("decided_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "leaves",
        sa.Column("decided_by_v1", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "leaves",
        sa.Column("decided_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("leaves", "decided_at")
    op.drop_column("leaves", "decided_by_v1")
    op.drop_column("leaves", "decided_by_user_id")
    op.drop_index("uq_notifications_school_idempotency", table_name="notifications")
    op.drop_column("notifications", "last_attempt_at")
    op.drop_column("notifications", "idempotency_key")
    op.drop_column("notifications", "max_retries")
    op.drop_column("notifications", "retry_count")
