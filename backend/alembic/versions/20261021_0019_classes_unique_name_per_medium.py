"""Unique active class names per school + medium.

Revision ID: 20261021_0019
Revises: 20261021_0018
Create Date: 2026-10-21

Additive only. Does not alter classes columns. Soft-deleted rows keep their
names; uniqueness applies while deleted_at IS NULL.

Uniqueness scope (confirmed from SchoolClass schema + product use):
  (school_id, medium_id, lower(btrim(name))) WHERE deleted_at IS NULL

Same class name may exist under different mediums in one school.
Do not apply until the target database is confirmed and existing duplicates
are reviewed with a read-only check, e.g.:

  SELECT school_id, medium_id, lower(btrim(name)) AS n, count(*)
  FROM classes
  WHERE deleted_at IS NULL
  GROUP BY 1, 2, 3
  HAVING count(*) > 1;
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261021_0019"
down_revision: Union[str, None] = "20261021_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_classes_school_medium_name_active",
        "classes",
        [sa.text("school_id"), sa.text("medium_id"), sa.text("lower(btrim(name))")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_classes_school_medium_name_active", table_name="classes")
