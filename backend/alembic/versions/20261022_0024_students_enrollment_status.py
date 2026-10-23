"""Add enrollment_status on students (admitted|active|inactive|transferred).

Revision ID: 20261022_0024
Revises: 20261022_0023
Create Date: 2026-10-22

Additive only. Does not drop columns or cascade-delete rows.
Backfills existing non-deleted rows to 'active' so current enrollments keep
working; new admissions start as 'admitted' in the application layer.

User.status (0/1) remains for login gates and is synced by the service layer.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0024"
down_revision: Union[str, None] = "20261022_0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "students",
        sa.Column(
            "enrollment_status",
            sa.String(length=32),
            nullable=False,
            server_default="admitted",
        ),
    )
    op.execute(
        sa.text(
            "UPDATE students SET enrollment_status = 'active' WHERE deleted_at IS NULL"
        )
    )
    op.create_index(
        "ix_students_enrollment_status",
        "students",
        ["enrollment_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_students_enrollment_status", table_name="students")
    op.drop_column("students", "enrollment_status")
