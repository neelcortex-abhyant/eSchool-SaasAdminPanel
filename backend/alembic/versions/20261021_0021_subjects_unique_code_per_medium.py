"""Unique active subject codes per school + medium.

Revision ID: 20261021_0021
Revises: 20261021_0020
Create Date: 2026-10-21

Additive only. Does not alter subjects columns.

Uniqueness scope (confirmed for Phase 6 Subject Management):
  (school_id, medium_id, lower(btrim(code))) WHERE deleted_at IS NULL
  AND code IS NOT NULL AND btrim(code) <> ''

Blank/null codes may repeat. Soft-deleted codes may be reused.
Same code under a different medium in one school is allowed.

Do not apply until the target database is confirmed and existing duplicates
are reviewed with a read-only check, e.g.:

  SELECT school_id, medium_id, lower(btrim(code)) AS c, count(*)
  FROM subjects
  WHERE deleted_at IS NULL AND code IS NOT NULL AND btrim(code) <> ''
  GROUP BY 1, 2, 3
  HAVING count(*) > 1;
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261021_0021"
down_revision: Union[str, None] = "20261021_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_subjects_school_medium_code_active",
        "subjects",
        [sa.text("school_id"), sa.text("medium_id"), sa.text("lower(btrim(code))")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND code IS NOT NULL AND btrim(code) <> ''"),
    )


def downgrade() -> None:
    op.drop_index("uq_subjects_school_medium_code_active", table_name="subjects")
