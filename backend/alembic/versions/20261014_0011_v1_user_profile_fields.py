"""Add school admin profile fields on v1_users.

Revision ID: 20261014_0011
Revises: 20261009_0010
Create Date: 2026-10-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_0011"
down_revision: Union[str, None] = "20261009_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("v1_users", sa.Column("country_code", sa.String(length=8), nullable=True))
    op.add_column("v1_users", sa.Column("gender", sa.String(length=16), nullable=True))
    op.add_column("v1_users", sa.Column("image", sa.String(length=255), nullable=True))
    op.add_column("v1_users", sa.Column("dob", sa.Date(), nullable=True))
    op.add_column("v1_users", sa.Column("current_address", sa.String(length=512), nullable=True))
    op.add_column("v1_users", sa.Column("permanent_address", sa.String(length=512), nullable=True))
    op.add_column(
        "v1_users",
        sa.Column("two_factor_enabled", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("v1_users", "two_factor_enabled")
    op.drop_column("v1_users", "permanent_address")
    op.drop_column("v1_users", "current_address")
    op.drop_column("v1_users", "dob")
    op.drop_column("v1_users", "image")
    op.drop_column("v1_users", "gender")
    op.drop_column("v1_users", "country_code")
