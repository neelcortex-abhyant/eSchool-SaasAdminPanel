"""Class timetable entries for school-admin scheduling.

Revision ID: 20261023_0032
Revises: 20261022_0031
Create Date: 2026-10-23

Additive only. Soft-delete friendly. No classroom column (deferred).
Does not apply automatically.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_0032"
down_revision: Union[str, None] = "20261022_0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "class_timetable_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column(
            "session_year_id",
            sa.Integer(),
            sa.ForeignKey("session_years.id"),
            nullable=False,
        ),
        sa.Column(
            "class_section_id",
            sa.Integer(),
            sa.ForeignKey("class_sections.id"),
            nullable=False,
        ),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("teacher_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=False),
        sa.Column("day", sa.String(length=16), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("end_time > start_time", name="ck_class_timetable_entries_time_order"),
    )
    op.create_index("ix_class_timetable_entries_school_id", "class_timetable_entries", ["school_id"])
    op.create_index(
        "ix_class_timetable_entries_session_year_id",
        "class_timetable_entries",
        ["session_year_id"],
    )
    op.create_index(
        "ix_class_timetable_entries_class_section_id",
        "class_timetable_entries",
        ["class_section_id"],
    )
    op.create_index(
        "ix_class_timetable_entries_subject_id",
        "class_timetable_entries",
        ["subject_id"],
    )
    op.create_index(
        "ix_class_timetable_entries_teacher_user_id",
        "class_timetable_entries",
        ["teacher_user_id"],
    )
    op.create_index(
        "ix_class_timetable_entries_staff_id",
        "class_timetable_entries",
        ["staff_id"],
    )
    op.create_index(
        "ix_class_timetable_entries_school_session_cs_day",
        "class_timetable_entries",
        ["school_id", "session_year_id", "class_section_id", "day"],
    )
    op.create_index(
        "ix_class_timetable_entries_school_teacher_day",
        "class_timetable_entries",
        ["school_id", "teacher_user_id", "day"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_class_timetable_entries_school_teacher_day",
        table_name="class_timetable_entries",
    )
    op.drop_index(
        "ix_class_timetable_entries_school_session_cs_day",
        table_name="class_timetable_entries",
    )
    op.drop_index("ix_class_timetable_entries_staff_id", table_name="class_timetable_entries")
    op.drop_index(
        "ix_class_timetable_entries_teacher_user_id",
        table_name="class_timetable_entries",
    )
    op.drop_index("ix_class_timetable_entries_subject_id", table_name="class_timetable_entries")
    op.drop_index(
        "ix_class_timetable_entries_class_section_id",
        table_name="class_timetable_entries",
    )
    op.drop_index(
        "ix_class_timetable_entries_session_year_id",
        table_name="class_timetable_entries",
    )
    op.drop_index("ix_class_timetable_entries_school_id", table_name="class_timetable_entries")
    op.drop_table("class_timetable_entries")
