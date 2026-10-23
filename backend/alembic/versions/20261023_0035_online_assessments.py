"""Online MCQ assessments, questions, attempts (Module 5).

Revision ID: 20261023_0035
Revises: 20261023_0034
Create Date: 2026-10-23

Additive only. Distinct from legacy ``exams`` and Laravel ``online_exams*``.
Does not apply automatically.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_0035"
down_revision: Union[str, None] = "20261023_0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "online_assessments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("session_year_id", sa.Integer(), sa.ForeignKey("session_years.id"), nullable=False),
        sa.Column("class_section_id", sa.Integer(), sa.ForeignKey("class_sections.id"), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("teacher_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("total_marks", sa.Float(), nullable=False),
        sa.Column("passing_marks", sa.Float(), nullable=False),
        sa.Column("available_from", sa.DateTime(), nullable=False),
        sa.Column("available_until", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("results_published", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'closed')",
            name="ck_online_assessments_status",
        ),
        sa.CheckConstraint("duration_minutes > 0", name="ck_online_assessments_duration"),
        sa.CheckConstraint("total_marks > 0", name="ck_online_assessments_total_marks"),
        sa.CheckConstraint("passing_marks >= 0", name="ck_online_assessments_passing_marks"),
        sa.CheckConstraint(
            "passing_marks <= total_marks",
            name="ck_online_assessments_passing_le_total",
        ),
        sa.CheckConstraint(
            "available_until > available_from",
            name="ck_online_assessments_window",
        ),
        sa.CheckConstraint(
            "results_published IN (0, 1)",
            name="ck_online_assessments_results_published",
        ),
    )
    op.create_index("ix_online_assessments_school_id", "online_assessments", ["school_id"])
    op.create_index("ix_online_assessments_session_year_id", "online_assessments", ["session_year_id"])
    op.create_index("ix_online_assessments_class_section_id", "online_assessments", ["class_section_id"])
    op.create_index("ix_online_assessments_subject_id", "online_assessments", ["subject_id"])
    op.create_index("ix_online_assessments_teacher_user_id", "online_assessments", ["teacher_user_id"])
    op.create_index("ix_online_assessments_staff_id", "online_assessments", ["staff_id"])
    op.create_index(
        "ix_online_assessments_school_session_cs",
        "online_assessments",
        ["school_id", "session_year_id", "class_section_id"],
    )
    op.create_index(
        "ix_online_assessments_school_subject",
        "online_assessments",
        ["school_id", "subject_id"],
    )
    op.create_index(
        "ix_online_assessments_school_status",
        "online_assessments",
        ["school_id", "status"],
    )

    op.create_table(
        "online_assessment_questions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column(
            "assessment_id",
            sa.Integer(),
            sa.ForeignKey("online_assessments.id"),
            nullable=False,
        ),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=True),
        sa.Column("question_type", sa.String(length=32), nullable=False, server_default="mcq"),
        sa.Column("marks", sa.Float(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "question_type IN ('mcq')",
            name="ck_online_assessment_questions_type",
        ),
        sa.CheckConstraint("marks > 0", name="ck_online_assessment_questions_marks"),
        sa.CheckConstraint("version >= 1", name="ck_online_assessment_questions_version"),
    )
    op.create_index(
        "ix_online_assessment_questions_school_id",
        "online_assessment_questions",
        ["school_id"],
    )
    op.create_index(
        "ix_online_assessment_questions_assessment_id",
        "online_assessment_questions",
        ["assessment_id"],
    )
    op.create_index(
        "ix_online_assessment_questions_assessment",
        "online_assessment_questions",
        ["school_id", "assessment_id"],
    )

    op.create_table(
        "online_assessment_choices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column(
            "question_id",
            sa.Integer(),
            sa.ForeignKey("online_assessment_questions.id"),
            nullable=False,
        ),
        sa.Column("choice_text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "is_correct IN (0, 1)",
            name="ck_online_assessment_choices_is_correct",
        ),
    )
    op.create_index(
        "ix_online_assessment_choices_school_id",
        "online_assessment_choices",
        ["school_id"],
    )
    op.create_index(
        "ix_online_assessment_choices_question_id",
        "online_assessment_choices",
        ["question_id"],
    )
    op.create_index(
        "ix_online_assessment_choices_question",
        "online_assessment_choices",
        ["school_id", "question_id"],
    )

    op.create_table(
        "online_assessment_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column(
            "assessment_id",
            sa.Integer(),
            sa.ForeignKey("online_assessments.id"),
            nullable=False,
        ),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="in_progress"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("percentage", sa.Float(), nullable=True),
        sa.Column("passed", sa.Integer(), nullable=True),
        sa.Column("answer_key_snapshot", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('in_progress', 'submitted', 'expired', 'evaluated')",
            name="ck_online_assessment_attempts_status",
        ),
        sa.CheckConstraint(
            "passed IS NULL OR passed IN (0, 1)",
            name="ck_online_assessment_attempts_passed",
        ),
    )
    op.create_index(
        "ix_online_assessment_attempts_school_id",
        "online_assessment_attempts",
        ["school_id"],
    )
    op.create_index(
        "ix_online_assessment_attempts_assessment_id",
        "online_assessment_attempts",
        ["assessment_id"],
    )
    op.create_index(
        "ix_online_assessment_attempts_student_id",
        "online_assessment_attempts",
        ["student_id"],
    )
    op.create_index(
        "ix_online_assessment_attempts_school_assessment",
        "online_assessment_attempts",
        ["school_id", "assessment_id"],
    )
    op.create_index(
        "ix_online_assessment_attempts_school_student",
        "online_assessment_attempts",
        ["school_id", "student_id"],
    )
    op.create_index(
        "uq_online_assessment_attempts_active",
        "online_assessment_attempts",
        ["assessment_id", "student_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "online_assessment_answers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column(
            "attempt_id",
            sa.Integer(),
            sa.ForeignKey("online_assessment_attempts.id"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            sa.Integer(),
            sa.ForeignKey("online_assessment_questions.id"),
            nullable=False,
        ),
        sa.Column(
            "choice_id",
            sa.Integer(),
            sa.ForeignKey("online_assessment_choices.id"),
            nullable=True,
        ),
        sa.Column("marks_awarded", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_online_assessment_answers_school_id",
        "online_assessment_answers",
        ["school_id"],
    )
    op.create_index(
        "ix_online_assessment_answers_attempt_id",
        "online_assessment_answers",
        ["attempt_id"],
    )
    op.create_index(
        "ix_online_assessment_answers_question_id",
        "online_assessment_answers",
        ["question_id"],
    )
    op.create_index(
        "ix_online_assessment_answers_choice_id",
        "online_assessment_answers",
        ["choice_id"],
    )
    op.create_index(
        "uq_online_assessment_answers_attempt_question",
        "online_assessment_answers",
        ["attempt_id", "question_id"],
        unique=True,
    )
    op.create_index(
        "ix_online_assessment_answers_school_attempt",
        "online_assessment_answers",
        ["school_id", "attempt_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_online_assessment_answers_school_attempt",
        table_name="online_assessment_answers",
    )
    op.drop_index(
        "uq_online_assessment_answers_attempt_question",
        table_name="online_assessment_answers",
    )
    op.drop_index("ix_online_assessment_answers_choice_id", table_name="online_assessment_answers")
    op.drop_index("ix_online_assessment_answers_question_id", table_name="online_assessment_answers")
    op.drop_index("ix_online_assessment_answers_attempt_id", table_name="online_assessment_answers")
    op.drop_index("ix_online_assessment_answers_school_id", table_name="online_assessment_answers")
    op.drop_table("online_assessment_answers")

    op.drop_index(
        "uq_online_assessment_attempts_active",
        table_name="online_assessment_attempts",
    )
    op.drop_index(
        "ix_online_assessment_attempts_school_student",
        table_name="online_assessment_attempts",
    )
    op.drop_index(
        "ix_online_assessment_attempts_school_assessment",
        table_name="online_assessment_attempts",
    )
    op.drop_index("ix_online_assessment_attempts_student_id", table_name="online_assessment_attempts")
    op.drop_index(
        "ix_online_assessment_attempts_assessment_id",
        table_name="online_assessment_attempts",
    )
    op.drop_index("ix_online_assessment_attempts_school_id", table_name="online_assessment_attempts")
    op.drop_table("online_assessment_attempts")

    op.drop_index("ix_online_assessment_choices_question", table_name="online_assessment_choices")
    op.drop_index("ix_online_assessment_choices_question_id", table_name="online_assessment_choices")
    op.drop_index("ix_online_assessment_choices_school_id", table_name="online_assessment_choices")
    op.drop_table("online_assessment_choices")

    op.drop_index(
        "ix_online_assessment_questions_assessment",
        table_name="online_assessment_questions",
    )
    op.drop_index(
        "ix_online_assessment_questions_assessment_id",
        table_name="online_assessment_questions",
    )
    op.drop_index(
        "ix_online_assessment_questions_school_id",
        table_name="online_assessment_questions",
    )
    op.drop_table("online_assessment_questions")

    op.drop_index("ix_online_assessments_school_status", table_name="online_assessments")
    op.drop_index("ix_online_assessments_school_subject", table_name="online_assessments")
    op.drop_index("ix_online_assessments_school_session_cs", table_name="online_assessments")
    op.drop_index("ix_online_assessments_staff_id", table_name="online_assessments")
    op.drop_index("ix_online_assessments_teacher_user_id", table_name="online_assessments")
    op.drop_index("ix_online_assessments_subject_id", table_name="online_assessments")
    op.drop_index("ix_online_assessments_class_section_id", table_name="online_assessments")
    op.drop_index("ix_online_assessments_session_year_id", table_name="online_assessments")
    op.drop_index("ix_online_assessments_school_id", table_name="online_assessments")
    op.drop_table("online_assessments")
