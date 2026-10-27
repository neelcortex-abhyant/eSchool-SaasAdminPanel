"""Academic management wave tables (grading, fees, transport, etc).

Revision ID: 20261027_0039
Revises: 20261025_0038
Create Date: 2026-10-27

Additive create_table only. Does not apply automatically.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261027_0039"
down_revision: Union[str, None] = "20261025_0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "grading_scales",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_grading_scales_school_id", "grading_scales", ['school_id'], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_grading_scales_school_name_active
        ON grading_scales (school_id, lower(btrim(name)))
        WHERE deleted_at IS NULL
        """
    )
    op.create_table(
        "grading_scale_bands",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("grading_scale_id", sa.Integer(), sa.ForeignKey("grading_scales.id"), nullable=False),
        sa.Column("letter", sa.String(length=32), nullable=False),
        sa.Column("min_percent", sa.Float(), nullable=False),
        sa.Column("max_percent", sa.Float(), nullable=False),
        sa.Column("grade_point", sa.Float(), nullable=True),
        sa.Column("remark", sa.String(length=255), nullable=True),
        sa.Column("is_pass", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_grading_scale_bands_scale", "grading_scale_bands", ['school_id', 'grading_scale_id'], unique=False)
    op.create_index("ix_grading_scale_bands_school_id", "grading_scale_bands", ['school_id'], unique=False)
    op.create_index("ix_grading_scale_bands_grading_scale_id", "grading_scale_bands", ['grading_scale_id'], unique=False)
    op.create_table(
        "report_cards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("grading_scale_id", sa.Integer(), sa.ForeignKey("grading_scales.id"), nullable=True),
        sa.Column("percentage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("letter_grade", sa.String(length=32), nullable=True),
        sa.Column("passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subjects_json", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_report_cards_student_id", "report_cards", ['student_id'], unique=False)
    op.create_index(
        "uq_report_cards_exam_student_active",
        "report_cards",
        ['exam_id', 'student_id'],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_report_cards_grading_scale_id", "report_cards", ['grading_scale_id'], unique=False)
    op.create_index("ix_report_cards_exam_id", "report_cards", ['exam_id'], unique=False)
    op.create_index("ix_report_cards_school_id", "report_cards", ['school_id'], unique=False)
    op.create_index("ix_report_cards_school_exam", "report_cards", ['school_id', 'exam_id'], unique=False)
    op.create_table(
        "question_bank_questions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=True),
        sa.Column("question_type", sa.String(length=32), nullable=False, server_default="mcq"),
        sa.Column("marks", sa.Float(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_question_bank_questions_school_subject", "question_bank_questions", ['school_id', 'subject_id'], unique=False)
    op.create_index("ix_question_bank_questions_school_id", "question_bank_questions", ['school_id'], unique=False)
    op.create_index("ix_question_bank_questions_subject_id", "question_bank_questions", ['subject_id'], unique=False)
    op.create_table(
        "question_bank_choices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("question_bank_questions.id"), nullable=False),
        sa.Column("choice_text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_question_bank_choices_question", "question_bank_choices", ['school_id', 'question_id'], unique=False)
    op.create_index("ix_question_bank_choices_question_id", "question_bank_choices", ['question_id'], unique=False)
    op.create_index("ix_question_bank_choices_school_id", "question_bank_choices", ['school_id'], unique=False)
    op.create_table(
        "admission_inquiries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("student_name", sa.String(length=255), nullable=False),
        sa.Column("parent_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("mobile", sa.String(length=64), nullable=True),
        sa.Column("class_interested", sa.String(length=128), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_admission_inquiries_school_id", "admission_inquiries", ['school_id'], unique=False)
    op.create_index("ix_admission_inquiries_school_status", "admission_inquiries", ['school_id', 'status'], unique=False)
    op.create_table(
        "student_electives",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("session_year_id", sa.Integer(), sa.ForeignKey("session_years.id"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_student_electives_school_id", "student_electives", ['school_id'], unique=False)
    op.create_index("ix_student_electives_session_year_id", "student_electives", ['session_year_id'], unique=False)
    op.create_index("ix_student_electives_subject_id", "student_electives", ['subject_id'], unique=False)
    op.create_index("ix_student_electives_student_id", "student_electives", ['student_id'], unique=False)
    op.create_index(
        "uq_student_electives_active",
        "student_electives",
        ['school_id', 'student_id', 'subject_id', 'session_year_id'],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "student_transfers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("from_class_section_id", sa.Integer(), nullable=True),
        sa.Column("to_school_name", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("transfer_date", sa.Date(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_student_transfers_school_id", "student_transfers", ['school_id'], unique=False)
    op.create_index("ix_student_transfers_student_id", "student_transfers", ['student_id'], unique=False)
    op.create_table(
        "student_promotions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("from_class_section_id", sa.Integer(), nullable=False),
        sa.Column("to_class_section_id", sa.Integer(), nullable=False),
        sa.Column("from_session_year_id", sa.Integer(), nullable=True),
        sa.Column("to_session_year_id", sa.Integer(), nullable=True),
        sa.Column("promoted_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_student_promotions_student_id", "student_promotions", ['student_id'], unique=False)
    op.create_index("ix_student_promotions_school_id", "student_promotions", ['school_id'], unique=False)
    op.create_table(
        "holidays",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_holidays_school_date", "holidays", ['school_id', 'holiday_date'], unique=False)
    op.create_index("ix_holidays_school_id", "holidays", ['school_id'], unique=False)
    op.create_table(
        "fee_types",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="other"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_fee_types_school_id", "fee_types", ['school_id'], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_fee_types_school_name_active
        ON fee_types (school_id, lower(btrim(name)))
        WHERE deleted_at IS NULL
        """
    )
    op.create_table(
        "fee_structures",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("session_year_id", sa.Integer(), sa.ForeignKey("session_years.id"), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=True),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_fee_structures_session_year_id", "fee_structures", ['session_year_id'], unique=False)
    op.create_index("ix_fee_structures_school_session", "fee_structures", ['school_id', 'session_year_id'], unique=False)
    op.create_index("ix_fee_structures_class_id", "fee_structures", ['class_id'], unique=False)
    op.create_index("ix_fee_structures_school_id", "fee_structures", ['school_id'], unique=False)
    op.create_table(
        "fee_structure_amounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("structure_id", sa.Integer(), sa.ForeignKey("fee_structures.id"), nullable=False),
        sa.Column("fee_type_id", sa.Integer(), sa.ForeignKey("fee_types.id"), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_fee_structure_amounts_structure_id", "fee_structure_amounts", ['structure_id'], unique=False)
    op.create_index("ix_fee_structure_amounts_fee_type_id", "fee_structure_amounts", ['fee_type_id'], unique=False)
    op.create_index("ix_fee_structure_amounts_school_id", "fee_structure_amounts", ['school_id'], unique=False)
    op.create_index(
        "uq_fee_structure_amounts_active",
        "fee_structure_amounts",
        ['structure_id', 'fee_type_id'],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "fee_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("structure_id", sa.Integer(), sa.ForeignKey("fee_structures.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "uq_fee_assignments_active",
        "fee_assignments",
        ['structure_id', 'student_id'],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_fee_assignments_structure_id", "fee_assignments", ['structure_id'], unique=False)
    op.create_index("ix_fee_assignments_student_id", "fee_assignments", ['student_id'], unique=False)
    op.create_index("ix_fee_assignments_school_id", "fee_assignments", ['school_id'], unique=False)
    op.create_table(
        "fee_concessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("structure_id", sa.Integer(), sa.ForeignKey("fee_structures.id"), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("value", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_fee_concessions_student_id", "fee_concessions", ['student_id'], unique=False)
    op.create_index("ix_fee_concessions_structure_id", "fee_concessions", ['structure_id'], unique=False)
    op.create_index("ix_fee_concessions_school_id", "fee_concessions", ['school_id'], unique=False)
    op.create_index(
        "uq_fee_concessions_active",
        "fee_concessions",
        ['student_id', 'structure_id'],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "fee_payments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("fee_assignments.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False, server_default="cash"),
        sa.Column("receipt_no", sa.String(length=64), nullable=True),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_fee_payments_student_id", "fee_payments", ['student_id'], unique=False)
    op.create_index("ix_fee_payments_assignment_id", "fee_payments", ['assignment_id'], unique=False)
    op.create_index("ix_fee_payments_school_id", "fee_payments", ['school_id'], unique=False)
    op.create_index(
        "uq_fee_payments_idempotency_active",
        "fee_payments",
        ['school_id', 'idempotency_key'],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "uq_fee_payments_assignment_receipt_active",
        "fee_payments",
        ['assignment_id', 'receipt_no'],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND receipt_no IS NOT NULL"),
    )
    op.create_table(
        "academic_semesters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("session_year_id", sa.Integer(), sa.ForeignKey("session_years.id"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_academic_semesters_school_name_session_active
        ON academic_semesters (school_id, session_year_id, lower(btrim(name)))
        WHERE deleted_at IS NULL
        """
    )
    op.create_index("ix_academic_semesters_school_id", "academic_semesters", ['school_id'], unique=False)
    op.create_index("ix_academic_semesters_session_year_id", "academic_semesters", ['session_year_id'], unique=False)
    op.create_table(
        "academic_streams",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_academic_streams_school_id", "academic_streams", ['school_id'], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_academic_streams_school_name_active
        ON academic_streams (school_id, lower(btrim(name)))
        WHERE deleted_at IS NULL
        """
    )
    op.create_table(
        "academic_shifts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_academic_shifts_school_id", "academic_shifts", ['school_id'], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_academic_shifts_school_name_active
        ON academic_shifts (school_id, lower(btrim(name)))
        WHERE deleted_at IS NULL
        """
    )
    op.create_table(
        "syllabi",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=True),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=True),
        sa.Column("session_year_id", sa.Integer(), sa.ForeignKey("session_years.id"), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_syllabi_school_id", "syllabi", ['school_id'], unique=False)
    op.create_index("ix_syllabi_subject_id", "syllabi", ['subject_id'], unique=False)
    op.create_index("ix_syllabi_school_class_subject", "syllabi", ['school_id', 'class_id', 'subject_id'], unique=False)
    op.create_index("ix_syllabi_session_year_id", "syllabi", ['session_year_id'], unique=False)
    op.create_index("ix_syllabi_class_id", "syllabi", ['class_id'], unique=False)
    op.create_table(
        "online_classes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("class_section_id", sa.Integer(), sa.ForeignKey("class_sections.id"), nullable=True),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=True),
        sa.Column("teacher_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("meeting_url", sa.String(length=1024), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_online_classes_class_section_id", "online_classes", ['class_section_id'], unique=False)
    op.create_index("ix_online_classes_school_id", "online_classes", ['school_id'], unique=False)
    op.create_index("ix_online_classes_subject_id", "online_classes", ['subject_id'], unique=False)
    op.create_index("ix_online_classes_school_scheduled", "online_classes", ['school_id', 'scheduled_at'], unique=False)
    op.create_index("ix_online_classes_teacher_user_id", "online_classes", ['teacher_user_id'], unique=False)
    op.create_table(
        "staff_attendance_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="present"),
        sa.Column("check_in", sa.Time(), nullable=True),
        sa.Column("check_out", sa.Time(), nullable=True),
        sa.Column("remark", sa.String(length=512), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_staff_attendance_records_school_id", "staff_attendance_records", ['school_id'], unique=False)
    op.create_index(
        "uq_staff_attendance_records_active",
        "staff_attendance_records",
        ['school_id', 'staff_id', 'attendance_date'],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_staff_attendance_records_staff_id", "staff_attendance_records", ['staff_id'], unique=False)
    op.create_table(
        "staff_qr_attendance_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token", sa.String(length=128), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_staff_qr_attendance_settings_school_id", "staff_qr_attendance_settings", ['school_id'], unique=False)
    op.create_index(
        "uq_staff_qr_attendance_settings_school_active",
        "staff_qr_attendance_settings",
        ['school_id'],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "staff_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assigned_to_staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_staff_tasks_school_id", "staff_tasks", ['school_id'], unique=False)
    op.create_index("ix_staff_tasks_assigned_to_staff_id", "staff_tasks", ['assigned_to_staff_id'], unique=False)
    op.create_index("ix_staff_tasks_school_status", "staff_tasks", ['school_id', 'status'], unique=False)
    op.create_table(
        "expense_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_expense_categories_school_id", "expense_categories", ['school_id'], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_expense_categories_school_name_active
        ON expense_categories (school_id, lower(btrim(name)))
        WHERE deleted_at IS NULL
        """
    )
    op.create_table(
        "income_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_income_categories_school_name_active
        ON income_categories (school_id, lower(btrim(name)))
        WHERE deleted_at IS NULL
        """
    )
    op.create_index("ix_income_categories_school_id", "income_categories", ['school_id'], unique=False)
    op.create_table(
        "income_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("income_categories.id"), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("income_date", sa.Date(), nullable=False),
        sa.Column("session_year_id", sa.Integer(), sa.ForeignKey("session_years.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_income_records_session_year_id", "income_records", ['session_year_id'], unique=False)
    op.create_index("ix_income_records_school_date", "income_records", ['school_id', 'income_date'], unique=False)
    op.create_index("ix_income_records_school_id", "income_records", ['school_id'], unique=False)
    op.create_index("ix_income_records_category_id", "income_records", ['category_id'], unique=False)
    op.create_table(
        "payroll_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("pay_day", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="INR"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "uq_payroll_settings_school_active",
        "payroll_settings",
        ['school_id'],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_payroll_settings_school_id", "payroll_settings", ['school_id'], unique=False)
    op.create_table(
        "payroll_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("period_label", sa.String(length=64), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_payroll_runs_school_period", "payroll_runs", ['school_id', 'period_label'], unique=False)
    op.create_index("ix_payroll_runs_school_id", "payroll_runs", ['school_id'], unique=False)
    op.create_table(
        "payroll_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("payroll_runs.id"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=False),
        sa.Column("gross", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("deductions", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("net", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_payroll_items_run_id", "payroll_items", ['run_id'], unique=False)
    op.create_index("ix_payroll_items_school_id", "payroll_items", ['school_id'], unique=False)
    op.create_index("ix_payroll_items_staff_id", "payroll_items", ['staff_id'], unique=False)
    op.create_index("ix_payroll_items_run", "payroll_items", ['school_id', 'run_id'], unique=False)
    op.create_table(
        "transport_vehicles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("registration_no", sa.String(length=64), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_transport_vehicles_school_reg_active
        ON transport_vehicles (school_id, lower(btrim(registration_no)))
        WHERE deleted_at IS NULL
        """
    )
    op.create_index("ix_transport_vehicles_school_id", "transport_vehicles", ['school_id'], unique=False)
    op.create_table(
        "transport_routes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("transport_vehicles.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_transport_routes_school_id", "transport_routes", ['school_id'], unique=False)
    op.create_index("ix_transport_routes_vehicle_id", "transport_routes", ['vehicle_id'], unique=False)
    op.create_table(
        "transport_stops",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("route_id", sa.Integer(), sa.ForeignKey("transport_routes.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("stop_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pickup_time", sa.Time(), nullable=True),
        sa.Column("drop_time", sa.Time(), nullable=True),
        sa.Column("landmark", sa.String(length=255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_transport_stops_school_id", "transport_stops", ['school_id'], unique=False)
    op.create_index("ix_transport_stops_route", "transport_stops", ['school_id', 'route_id'], unique=False)
    op.create_index("ix_transport_stops_route_id", "transport_stops", ['route_id'], unique=False)
    op.create_table(
        "student_transport_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("route_id", sa.Integer(), sa.ForeignKey("transport_routes.id"), nullable=False),
        sa.Column("stop_id", sa.Integer(), sa.ForeignKey("transport_stops.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_student_transport_assignments_route_id", "student_transport_assignments", ['route_id'], unique=False)
    op.create_index("ix_student_transport_assignments_school_id", "student_transport_assignments", ['school_id'], unique=False)
    op.create_index("ix_student_transport_assignments_stop_id", "student_transport_assignments", ['stop_id'], unique=False)
    op.create_index(
        "uq_student_transport_assignments_active",
        "student_transport_assignments",
        ['school_id', 'student_id'],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_student_transport_assignments_student_id", "student_transport_assignments", ['student_id'], unique=False)
    op.create_table(
        "certificate_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("template_type", sa.String(length=64), nullable=False, server_default="general"),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_certificate_templates_school_id", "certificate_templates", ['school_id'], unique=False)
    op.create_table(
        "certificate_issues",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("certificate_templates.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("certificate_no", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_certificate_issues_student_id", "certificate_issues", ['student_id'], unique=False)
    op.create_index("ix_certificate_issues_school_id", "certificate_issues", ['school_id'], unique=False)
    op.create_index(
        "uq_certificate_issues_no_active",
        "certificate_issues",
        ['school_id', 'certificate_no'],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_certificate_issues_template_id", "certificate_issues", ['template_id'], unique=False)
    op.create_table(
        "id_card_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("front_template", sa.Text(), nullable=True),
        sa.Column("back_template", sa.Text(), nullable=True),
        sa.Column("show_fields_json", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "uq_id_card_settings_school_active",
        "id_card_settings",
        ['school_id'],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_id_card_settings_school_id", "id_card_settings", ['school_id'], unique=False)
    op.create_table(
        "diary_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_diary_categories_school_id", "diary_categories", ['school_id'], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_diary_categories_school_name_active
        ON diary_categories (school_id, lower(btrim(name)))
        WHERE deleted_at IS NULL
        """
    )
    op.create_table(
        "student_diary_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("diary_categories.id"), nullable=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_student_diary_entries_school_id", "student_diary_entries", ['school_id'], unique=False)
    op.create_index("ix_student_diary_entries_school_date", "student_diary_entries", ['school_id', 'entry_date'], unique=False)
    op.create_index("ix_student_diary_entries_student_id", "student_diary_entries", ['student_id'], unique=False)
    op.create_index("ix_student_diary_entries_category_id", "student_diary_entries", ['category_id'], unique=False)
    op.create_table(
        "school_sliders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("link_url", sa.String(length=1024), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_school_sliders_school_id", "school_sliders", ['school_id'], unique=False)
    op.create_table(
        "school_gallery_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_school_gallery_items_school_id", "school_gallery_items", ['school_id'], unique=False)


def downgrade() -> None:
    op.drop_table("school_gallery_items")
    op.drop_table("school_sliders")
    op.drop_table("student_diary_entries")
    op.drop_table("diary_categories")
    op.drop_table("id_card_settings")
    op.drop_table("certificate_issues")
    op.drop_table("certificate_templates")
    op.drop_table("student_transport_assignments")
    op.drop_table("transport_stops")
    op.drop_table("transport_routes")
    op.drop_table("transport_vehicles")
    op.drop_table("payroll_items")
    op.drop_table("payroll_runs")
    op.drop_table("payroll_settings")
    op.drop_table("income_records")
    op.drop_table("income_categories")
    op.drop_table("expense_categories")
    op.drop_table("staff_tasks")
    op.drop_table("staff_qr_attendance_settings")
    op.drop_table("staff_attendance_records")
    op.drop_table("online_classes")
    op.drop_table("syllabi")
    op.drop_table("academic_shifts")
    op.drop_table("academic_streams")
    op.drop_table("academic_semesters")
    op.drop_table("fee_payments")
    op.drop_table("fee_concessions")
    op.drop_table("fee_assignments")
    op.drop_table("fee_structure_amounts")
    op.drop_table("fee_structures")
    op.drop_table("fee_types")
    op.drop_table("holidays")
    op.drop_table("student_promotions")
    op.drop_table("student_transfers")
    op.drop_table("student_electives")
    op.drop_table("admission_inquiries")
    op.drop_table("question_bank_choices")
    op.drop_table("question_bank_questions")
    op.drop_table("report_cards")
    op.drop_table("grading_scale_bands")
    op.drop_table("grading_scales")
