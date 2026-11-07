"""Students admission_no unique per school+branch (approved per-branch behavior).

Revision ID: 20261106_0047
Revises: 20261105_0046
Create Date: 2026-11-06

Drops school-global uq_students_school_admission_no_active and replaces with
(school_id, branch_id, lower(btrim(admission_no))) among active rows with
branch_id set. Do not apply to Neon without explicit approval.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261106_0047"
down_revision: Union[str, None] = "20261105_0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    try:
        op.drop_index("uq_students_school_admission_no_active", table_name="students")
    except Exception:
        pass
    op.create_index(
        "uq_students_school_branch_admission_no_active",
        "students",
        ["school_id", "branch_id", sa.text("lower(btrim(admission_no))")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND branch_id IS NOT NULL"),
    )


def downgrade() -> None:
    try:
        op.drop_index(
            "uq_students_school_branch_admission_no_active", table_name="students"
        )
    except Exception:
        pass
    op.create_index(
        "uq_students_school_admission_no_active",
        "students",
        ["school_id", sa.text("lower(btrim(admission_no))")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
