"""Super Admin branch creation permission and per-school branch quota.

Revision ID: 20261106_0048
Revises: 20261106_0047
Create Date: 2026-11-06

Adds schools.branch_creation_enabled (default false) and schools.max_branches
(default 1, including the default Main branch). Does not insert, update, or
delete school_branches rows. Do not apply to Neon without explicit approval.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261106_0048"
down_revision: Union[str, None] = "20261106_0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "schools",
        sa.Column(
            "branch_creation_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "schools",
        sa.Column("max_branches", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint(
        "ck_schools_max_branches_at_least_one",
        "schools",
        "max_branches >= 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_schools_max_branches_at_least_one", "schools", type_="check")
    op.drop_column("schools", "max_branches")
    op.drop_column("schools", "branch_creation_enabled")
