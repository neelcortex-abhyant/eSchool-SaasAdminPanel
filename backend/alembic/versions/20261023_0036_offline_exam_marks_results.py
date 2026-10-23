"""Offline exam schedules, marks, audits, results (Module 6).

Revision ID: 20261023_0036
Revises: 20261023_0035
Create Date: 2026-10-23

Additive only. Extends ``exams``; new offline_exam_* tables (not Laravel names).
Does not apply automatically.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_0036"
down_revision: Union[str, None] = "20261023_0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exams",
        sa.Column("class_section_id", sa.Integer(), sa.ForeignKey("class_sections.id"), nullable=True),
    )
    op.add_column("exams", sa.Column("exam_type", sa.String(length=64), nullable=True))
    op.add_column("exams", sa.Column("exam_date", sa.Date(), nullable=True))
    op.add_column("exams", sa.Column("results_processed_at", sa.DateTime(), nullable=True))
    op.create_index("ix_exams_class_section_id", "exams", ["class_section_id"])
    op.create_index("ix_exams_school_session", "exams", ["school_id", "session_year_id"])
    op.create_index(
        "ix_exams_school_class_section",
        "exams",
        ["school_id", "class_section_id"],
    )

    op.create_table(
        "offline_exam_schedules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id"), nullable=False),
        sa.Column("session_year_id", sa.Integer(), sa.ForeignKey("session_years.id"), nullable=False),
        sa.Column("class_section_id", sa.Integer(), sa.ForeignKey("class_sections.id"), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("teacher_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=True),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("max_marks", sa.Float(), nullable=False),
        sa.Column("passing_marks", sa.Float(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("max_marks > 0", name="ck_offline_exam_schedules_max_marks"),
        sa.CheckConstraint("passing_marks >= 0", name="ck_offline_exam_schedules_passing"),
        sa.CheckConstraint(
            "passing_marks <= max_marks",
            name="ck_offline_exam_schedules_passing_le_max",
        ),
        sa.CheckConstraint(
            "end_time IS NULL OR start_time IS NULL OR end_time > start_time",
            name="ck_offline_exam_schedules_time_order",
        ),
    )
    op.create_index("ix_offline_exam_schedules_school_id", "offline_exam_schedules", ["school_id"])
    op.create_index("ix_offline_exam_schedules_exam_id", "offline_exam_schedules", ["exam_id"])
    op.create_index(
        "ix_offline_exam_schedules_session_year_id",
        "offline_exam_schedules",
        ["session_year_id"],
    )
    op.create_index(
        "ix_offline_exam_schedules_class_section_id",
        "offline_exam_schedules",
        ["class_section_id"],
    )
    op.create_index("ix_offline_exam_schedules_subject_id", "offline_exam_schedules", ["subject_id"])
    op.create_index(
        "ix_offline_exam_schedules_teacher_user_id",
        "offline_exam_schedules",
        ["teacher_user_id"],
    )
    op.create_index("ix_offline_exam_schedules_staff_id", "offline_exam_schedules", ["staff_id"])
    op.create_index(
        "ix_offline_exam_schedules_school_cs_date",
        "offline_exam_schedules",
        ["school_id", "class_section_id", "exam_date"],
    )
    op.create_index(
        "uq_offline_exam_schedules_active",
        "offline_exam_schedules",
        ["exam_id", "class_section_id", "subject_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "offline_exam_marks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id"), nullable=False),
        sa.Column(
            "schedule_id",
            sa.Integer(),
            sa.ForeignKey("offline_exam_schedules.id"),
            nullable=False,
        ),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("marks_obtained", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="present"),
        sa.Column("evaluated_by_v1_user_id", sa.String(length=36), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('present', 'absent', 'withheld')",
            name="ck_offline_exam_marks_status",
        ),
        sa.CheckConstraint(
            "marks_obtained IS NULL OR marks_obtained >= 0",
            name="ck_offline_exam_marks_obtained",
        ),
    )
    op.create_index("ix_offline_exam_marks_school_id", "offline_exam_marks", ["school_id"])
    op.create_index("ix_offline_exam_marks_exam_id", "offline_exam_marks", ["exam_id"])
    op.create_index("ix_offline_exam_marks_schedule_id", "offline_exam_marks", ["schedule_id"])
    op.create_index("ix_offline_exam_marks_student_id", "offline_exam_marks", ["student_id"])
    op.create_index(
        "ix_offline_exam_marks_school_exam",
        "offline_exam_marks",
        ["school_id", "exam_id"],
    )
    op.create_index(
        "uq_offline_exam_marks_active",
        "offline_exam_marks",
        ["schedule_id", "student_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "offline_exam_mark_audits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("mark_id", sa.Integer(), sa.ForeignKey("offline_exam_marks.id"), nullable=False),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("previous_marks", sa.Float(), nullable=True),
        sa.Column("new_marks", sa.Float(), nullable=True),
        sa.Column("previous_status", sa.String(length=32), nullable=False),
        sa.Column("new_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=False),
        sa.Column("actor_v1_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_offline_exam_mark_audits_school_id",
        "offline_exam_mark_audits",
        ["school_id"],
    )
    op.create_index("ix_offline_exam_mark_audits_mark_id", "offline_exam_mark_audits", ["mark_id"])
    op.create_index(
        "ix_offline_exam_mark_audits_mark",
        "offline_exam_mark_audits",
        ["school_id", "mark_id"],
    )

    op.create_table(
        "offline_exam_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("total_max_marks", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_obtained", sa.Float(), nullable=False, server_default="0"),
        sa.Column("percentage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subjects_json", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "passed IS NULL OR passed IN (0, 1)",
            name="ck_offline_exam_results_passed",
        ),
    )
    op.create_index("ix_offline_exam_results_school_id", "offline_exam_results", ["school_id"])
    op.create_index("ix_offline_exam_results_exam_id", "offline_exam_results", ["exam_id"])
    op.create_index("ix_offline_exam_results_student_id", "offline_exam_results", ["student_id"])
    op.create_index(
        "ix_offline_exam_results_school_exam",
        "offline_exam_results",
        ["school_id", "exam_id"],
    )
    op.create_index(
        "uq_offline_exam_results_active",
        "offline_exam_results",
        ["exam_id", "student_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_offline_exam_results_active", table_name="offline_exam_results")
    op.drop_index("ix_offline_exam_results_school_exam", table_name="offline_exam_results")
    op.drop_index("ix_offline_exam_results_student_id", table_name="offline_exam_results")
    op.drop_index("ix_offline_exam_results_exam_id", table_name="offline_exam_results")
    op.drop_index("ix_offline_exam_results_school_id", table_name="offline_exam_results")
    op.drop_table("offline_exam_results")

    op.drop_index("ix_offline_exam_mark_audits_mark", table_name="offline_exam_mark_audits")
    op.drop_index("ix_offline_exam_mark_audits_mark_id", table_name="offline_exam_mark_audits")
    op.drop_index("ix_offline_exam_mark_audits_school_id", table_name="offline_exam_mark_audits")
    op.drop_table("offline_exam_mark_audits")

    op.drop_index("uq_offline_exam_marks_active", table_name="offline_exam_marks")
    op.drop_index("ix_offline_exam_marks_school_exam", table_name="offline_exam_marks")
    op.drop_index("ix_offline_exam_marks_student_id", table_name="offline_exam_marks")
    op.drop_index("ix_offline_exam_marks_schedule_id", table_name="offline_exam_marks")
    op.drop_index("ix_offline_exam_marks_exam_id", table_name="offline_exam_marks")
    op.drop_index("ix_offline_exam_marks_school_id", table_name="offline_exam_marks")
    op.drop_table("offline_exam_marks")

    op.drop_index("uq_offline_exam_schedules_active", table_name="offline_exam_schedules")
    op.drop_index("ix_offline_exam_schedules_school_cs_date", table_name="offline_exam_schedules")
    op.drop_index("ix_offline_exam_schedules_staff_id", table_name="offline_exam_schedules")
    op.drop_index("ix_offline_exam_schedules_teacher_user_id", table_name="offline_exam_schedules")
    op.drop_index("ix_offline_exam_schedules_subject_id", table_name="offline_exam_schedules")
    op.drop_index("ix_offline_exam_schedules_class_section_id", table_name="offline_exam_schedules")
    op.drop_index("ix_offline_exam_schedules_session_year_id", table_name="offline_exam_schedules")
    op.drop_index("ix_offline_exam_schedules_exam_id", table_name="offline_exam_schedules")
    op.drop_index("ix_offline_exam_schedules_school_id", table_name="offline_exam_schedules")
    op.drop_table("offline_exam_schedules")

    op.drop_index("ix_exams_school_class_section", table_name="exams")
    op.drop_index("ix_exams_school_session", table_name="exams")
    op.drop_index("ix_exams_class_section_id", table_name="exams")
    op.drop_column("exams", "results_processed_at")
    op.drop_column("exams", "exam_date")
    op.drop_column("exams", "exam_type")
    op.drop_column("exams", "class_section_id")
