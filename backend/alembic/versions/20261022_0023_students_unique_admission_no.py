"""Unique active student admission/GR number per school.

Revision ID: 20261022_0023
Revises: 20261021_0022
Create Date: 2026-10-22

Additive only. Does not alter students columns or cascade-delete rows.
Soft-deleted admission numbers may be reused.

## Preflight (read-only) before apply

  SELECT school_id, lower(btrim(admission_no)) AS n, count(*), array_agg(id ORDER BY id)
  FROM students
  WHERE deleted_at IS NULL
  GROUP BY school_id, lower(btrim(admission_no))
  HAVING count(*) > 1;

Resolve duplicates manually before upgrade. Do not auto-delete.

Application layer already enforces the same rule in create_student / update_student.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0023"
down_revision: Union[str, None] = "20261021_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_students_school_admission_no_active",
        "students",
        [sa.text("school_id"), sa.text("lower(btrim(admission_no))")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_students_school_admission_no_active", table_name="students")
