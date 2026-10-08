"""Phase 4: plan pricing/limits on existing packages table.

Revision ID: 20261007_0006
Revises: 20261007_0005
Create Date: 2026-10-07

Additive only. Does not create a separate plans table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0006"
down_revision: Union[str, None] = "20261007_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "packages",
        sa.Column("monthly_price", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "packages",
        sa.Column("yearly_price", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column("packages", sa.Column("student_limit", sa.Integer(), nullable=True))
    op.add_column("packages", sa.Column("staff_limit", sa.Integer(), nullable=True))
    op.create_index("ix_packages_name", "packages", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_packages_name", table_name="packages")
    op.drop_column("packages", "staff_limit")
    op.drop_column("packages", "student_limit")
    op.drop_column("packages", "yearly_price")
    op.drop_column("packages", "monthly_price")
