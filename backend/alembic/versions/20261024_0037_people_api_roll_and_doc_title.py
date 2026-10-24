"""People API: student roll unique index + person_documents.title.

Revision ID: 20261024_0037
Revises: 20261023_0036
Create Date: 2026-10-24

Additive only. Does not apply automatically.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261024_0037"
down_revision: Union[str, None] = "20261023_0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "person_documents",
        sa.Column("title", sa.String(length=120), nullable=True),
    )
    op.create_index(
        "uq_students_school_session_cs_roll_active",
        "students",
        ["school_id", "session_year_id", "class_section_id", "roll_number"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND roll_number IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_students_school_session_cs_roll_active",
        table_name="students",
    )
    op.drop_column("person_documents", "title")
