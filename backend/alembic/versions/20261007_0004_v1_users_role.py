"""Add role column to v1_users for Super Admin authorization.

Revision ID: 20261007_0004
Revises: 20261005_0003
Create Date: 2026-10-07

Additive only: existing rows receive role='user'. Does not drop or rename columns.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0004"
down_revision: Union[str, None] = "20261005_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "v1_users",
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
    )
    op.create_index("ix_v1_users_role", "v1_users", ["role"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_v1_users_role", table_name="v1_users")
    op.drop_column("v1_users", "role")
