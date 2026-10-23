"""Unique attendance per school, session, student, and date.

Revision ID: 20261022_0030
Revises: 20261022_0029
Create Date: 2026-10-22

Additive only. Creates a unique index so a student cannot be marked twice for
the same session day.

PREFLIGHT (required before upgrade on non-empty DBs):
  SELECT school_id, session_year_id, student_id, date, COUNT(*)
  FROM attendances
  GROUP BY 1, 2, 3, 4
  HAVING COUNT(*) > 1;

Resolve duplicates before applying. This revision does not rewrite student_id
identity (students.id vs users.id) — see Module 4 audit.

Leave status uses integer type=3 in application code (no DDL). Historical
values remain 0=absent, 1=present, 2=late.

Does not apply automatically.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0030"
down_revision: Union[str, None] = "20261022_0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_attendances_school_session_student_date",
        "attendances",
        ["school_id", "session_year_id", "student_id", "date"],
        unique=True,
    )
    op.create_index(
        "ix_attendances_school_date",
        "attendances",
        ["school_id", "date"],
    )
    op.create_index(
        "ix_attendances_school_class_section_date",
        "attendances",
        ["school_id", "class_section_id", "date"],
    )


def downgrade() -> None:
    op.drop_index("ix_attendances_school_class_section_date", table_name="attendances")
    op.drop_index("ix_attendances_school_date", table_name="attendances")
    op.drop_index("uq_attendances_school_session_student_date", table_name="attendances")
