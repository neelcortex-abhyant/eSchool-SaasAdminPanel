"""Unique active class–section mappings per school.

Revision ID: 20261021_0020
Revises: 20261021_0019
Create Date: 2026-10-21

Additive only. Does not alter sections or class_sections columns.

Uniqueness scopes (app-enforced in Phase 5; this index hardens mapping integrity):
  class_sections: (school_id, class_id, section_id) WHERE deleted_at IS NULL

Section *names* within a class are enforced in the service layer by joining
sections ↔ class_sections (case-insensitive). A pure SQL unique index on
section name per class would require a denormalized name column on
class_sections and is intentionally not added here.

Do not apply until the target database is confirmed and existing duplicates
are reviewed with a read-only check, e.g.:

  SELECT school_id, class_id, section_id, count(*)
  FROM class_sections
  WHERE deleted_at IS NULL
  GROUP BY 1, 2, 3
  HAVING count(*) > 1;
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261021_0020"
down_revision: Union[str, None] = "20261021_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_class_sections_school_class_section_active",
        "class_sections",
        ["school_id", "class_id", "section_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_class_sections_school_class_section_active", table_name="class_sections")
