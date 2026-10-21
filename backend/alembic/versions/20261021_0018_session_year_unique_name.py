"""Unique active academic session names per school.

Revision ID: 20261021_0018
Revises: 20261021_0017
Create Date: 2026-10-21

Additive only. Does not alter session_years columns. Soft-deleted rows keep
their names so historical records are preserved; uniqueness applies while
deleted_at IS NULL.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261021_0018"
down_revision: Union[str, None] = "20261021_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_session_years_school_name_active",
        "session_years",
        [sa.text("school_id"), sa.text("lower(btrim(name))")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_session_years_school_name_active", table_name="session_years")
