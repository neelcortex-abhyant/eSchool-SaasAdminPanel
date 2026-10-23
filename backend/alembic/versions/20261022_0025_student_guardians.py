"""Add student_guardians association and backfill from students.guardian_id.

Revision ID: 20261022_0025
Revises: 20261022_0024
Create Date: 2026-10-22

Additive only. Does not drop students.guardian_id.
Backfills one primary row per live student that has a guardian_id.
Does not assign Spatie Guardian roles (see revision 20261022_0026).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0025"
down_revision: Union[str, None] = "20261022_0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "student_guardians",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column(
            "guardian_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "relationship_type",
            sa.String(length=32),
            nullable=False,
            server_default="guardian",
        ),
        sa.Column(
            "is_primary",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_student_guardians_school_id", "student_guardians", ["school_id"])
    op.create_index(
        "ix_student_guardians_guardian_user_id",
        "student_guardians",
        ["guardian_user_id"],
    )
    op.create_index("ix_student_guardians_student_id", "student_guardians", ["student_id"])
    op.create_index(
        "uq_student_guardians_active_pair",
        "student_guardians",
        ["student_id", "guardian_user_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_student_guardians_one_primary",
        "student_guardians",
        ["student_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND is_primary = 1"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO student_guardians (
                school_id, student_id, guardian_user_id,
                relationship_type, is_primary, created_at, updated_at
            )
            SELECT
                s.school_id, s.id, s.guardian_id,
                'guardian', 1, NOW(), NOW()
            FROM students s
            WHERE s.deleted_at IS NULL
              AND s.guardian_id IS NOT NULL
              AND EXISTS (
                SELECT 1 FROM users u WHERE u.id = s.guardian_id
              )
              AND NOT EXISTS (
                SELECT 1 FROM student_guardians sg
                WHERE sg.student_id = s.id
                  AND sg.guardian_user_id = s.guardian_id
                  AND sg.deleted_at IS NULL
              )
            """
        )
    )


def downgrade() -> None:
    op.drop_index("uq_student_guardians_one_primary", table_name="student_guardians")
    op.drop_index("uq_student_guardians_active_pair", table_name="student_guardians")
    op.drop_index("ix_student_guardians_student_id", table_name="student_guardians")
    op.drop_index("ix_student_guardians_guardian_user_id", table_name="student_guardians")
    op.drop_index("ix_student_guardians_school_id", table_name="student_guardians")
    op.drop_table("student_guardians")
