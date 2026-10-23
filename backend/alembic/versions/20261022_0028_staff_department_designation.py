"""Add nullable department and designation on staffs.

Revision ID: 20261022_0028
Revises: 20261022_0027
Create Date: 2026-10-22

Additive only. Free-text columns (no lookup tables in this phase).
Existing rows remain NULL. Does not assign Spatie roles.
Does not apply automatically — review and run alembic upgrade when approved.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0028"
down_revision: Union[str, None] = "20261022_0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "staffs",
        sa.Column("department", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "staffs",
        sa.Column("designation", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("staffs", "designation")
    op.drop_column("staffs", "department")
