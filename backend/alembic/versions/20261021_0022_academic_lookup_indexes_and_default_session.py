"""Academic lookup indexes + at-most-one default session per school.

Revision ID: 20261021_0022
Revises: 20261021_0021
Create Date: 2026-10-21

Additive only. Does not alter column types, drop data, or add cascading FKs.

## What this resolves

1. Filter/join performance on class_sections and medium FKs that the legacy
   schema only indexed by school_id (0003). Assignments and section APIs filter
   by class_id / section_id frequently.
2. DB hardening for the existing app rule \"at most one active default session
   per school\" (Phase 3 activate). Zero defaults remain allowed.

## What this deliberately does NOT do

- Does not add FKs from legacy session_years/classes/sections/subjects/
  class_sections integer columns to schools/mediums/classes/sections.
  Those tables predate V1 FKs; orphans are rejected in services. Adding FKs
  requires a separate orphan audit and product approval.
- Does not add ON DELETE CASCADE (would erase historical academic rows).
- Does not rewrite 0017–0021.

## Preflight (read-only) before apply

Multiple active defaults (must be empty or cleaned manually before upgrade):

  SELECT school_id, count(*)
  FROM session_years
  WHERE deleted_at IS NULL AND \"default\" = 1
  GROUP BY school_id
  HAVING count(*) > 1;

Also run the duplicate checks documented in 0018–0021 if those revisions
have not been applied yet.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261021_0022"
down_revision: Union[str, None] = "20261021_0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_class_sections_class_id", "class_sections", ["class_id"])
    op.create_index("ix_class_sections_section_id", "class_sections", ["section_id"])
    op.create_index("ix_class_sections_medium_id", "class_sections", ["medium_id"])
    op.create_index("ix_classes_medium_id", "classes", ["medium_id"])
    op.create_index("ix_subjects_medium_id", "subjects", ["medium_id"])
    op.create_index(
        "uq_session_years_school_default_active",
        "session_years",
        ["school_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND \"default\" = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_session_years_school_default_active", table_name="session_years")
    op.drop_index("ix_subjects_medium_id", table_name="subjects")
    op.drop_index("ix_classes_medium_id", table_name="classes")
    op.drop_index("ix_class_sections_medium_id", table_name="class_sections")
    op.drop_index("ix_class_sections_section_id", table_name="class_sections")
    op.drop_index("ix_class_sections_class_id", table_name="class_sections")
