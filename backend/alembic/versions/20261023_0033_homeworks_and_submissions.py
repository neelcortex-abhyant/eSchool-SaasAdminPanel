"""Homework briefs and student submissions (Module 3).

Revision ID: 20261023_0033
Revises: 20261023_0032
Create Date: 2026-10-23

Additive only. Soft-delete friendly. Does not apply automatically.
Distinct from legacy Laravel ``assignments`` / ``assignment_submissions`` names.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_0033"
down_revision: Union[str, None] = "20261023_0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "homeworks",
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
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("assigned_date", sa.Date(), nullable=False),
        sa.Column("deadline_at", sa.DateTime(), nullable=False),
        sa.Column("max_marks", sa.Float(), nullable=True),
        sa.Column("allow_late", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("attachments_json", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "max_marks IS NULL OR max_marks >= 0",
            name="ck_homeworks_max_marks",
        ),
        sa.CheckConstraint("allow_late IN (0, 1)", name="ck_homeworks_allow_late"),
    )
    op.create_index("ix_homeworks_school_id", "homeworks", ["school_id"])
    op.create_index("ix_homeworks_session_year_id", "homeworks", ["session_year_id"])
    op.create_index("ix_homeworks_class_section_id", "homeworks", ["class_section_id"])
    op.create_index("ix_homeworks_subject_id", "homeworks", ["subject_id"])
    op.create_index("ix_homeworks_teacher_user_id", "homeworks", ["teacher_user_id"])
    op.create_index("ix_homeworks_staff_id", "homeworks", ["staff_id"])
    op.create_index(
        "ix_homeworks_school_session_cs",
        "homeworks",
        ["school_id", "session_year_id", "class_section_id"],
    )
    op.create_index(
        "ix_homeworks_school_teacher",
        "homeworks",
        ["school_id", "teacher_user_id"],
    )
    op.create_index(
        "ix_homeworks_school_deadline",
        "homeworks",
        ["school_id", "deadline_at"],
    )

    op.create_table(
        "homework_submissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("homework_id", sa.Integer(), sa.ForeignKey("homeworks.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("text_response", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="submitted"),
        sa.Column("is_late", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("marks", sa.Float(), nullable=True),
        sa.Column("grade", sa.String(length=64), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("evaluated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=True),
        sa.Column("attachments_json", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('submitted', 'graded')",
            name="ck_homework_submissions_status",
        ),
        sa.CheckConstraint("is_late IN (0, 1)", name="ck_homework_submissions_is_late"),
        sa.CheckConstraint(
            "marks IS NULL OR marks >= 0",
            name="ck_homework_submissions_marks",
        ),
    )
    op.create_index("ix_homework_submissions_school_id", "homework_submissions", ["school_id"])
    op.create_index("ix_homework_submissions_homework_id", "homework_submissions", ["homework_id"])
    op.create_index("ix_homework_submissions_student_id", "homework_submissions", ["student_id"])
    op.create_index(
        "ix_homework_submissions_evaluated_by_user_id",
        "homework_submissions",
        ["evaluated_by_user_id"],
    )
    op.create_index(
        "ix_homework_submissions_school_homework",
        "homework_submissions",
        ["school_id", "homework_id"],
    )
    op.create_index(
        "ix_homework_submissions_school_student",
        "homework_submissions",
        ["school_id", "student_id"],
    )
    op.create_index(
        "uq_homework_submissions_active",
        "homework_submissions",
        ["homework_id", "student_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_homework_submissions_active",
        table_name="homework_submissions",
    )
    op.drop_index(
        "ix_homework_submissions_school_student",
        table_name="homework_submissions",
    )
    op.drop_index(
        "ix_homework_submissions_school_homework",
        table_name="homework_submissions",
    )
    op.drop_index(
        "ix_homework_submissions_evaluated_by_user_id",
        table_name="homework_submissions",
    )
    op.drop_index("ix_homework_submissions_student_id", table_name="homework_submissions")
    op.drop_index("ix_homework_submissions_homework_id", table_name="homework_submissions")
    op.drop_index("ix_homework_submissions_school_id", table_name="homework_submissions")
    op.drop_table("homework_submissions")

    op.drop_index("ix_homeworks_school_deadline", table_name="homeworks")
    op.drop_index("ix_homeworks_school_teacher", table_name="homeworks")
    op.drop_index("ix_homeworks_school_session_cs", table_name="homeworks")
    op.drop_index("ix_homeworks_staff_id", table_name="homeworks")
    op.drop_index("ix_homeworks_teacher_user_id", table_name="homeworks")
    op.drop_index("ix_homeworks_subject_id", table_name="homeworks")
    op.drop_index("ix_homeworks_class_section_id", table_name="homeworks")
    op.drop_index("ix_homeworks_session_year_id", table_name="homeworks")
    op.drop_index("ix_homeworks_school_id", table_name="homeworks")
    op.drop_table("homeworks")
