"""School Admin people: student status, guardians, employee fields, documents.

Revision ID: 20261022_0023
Revises: 20261021_0022
Create Date: 2026-10-22

- students: status
- staffs: employee_type (existing rows become teachers), employee_code,
  department, designation, joining_date, employment_type
- student_guardians, documents (new)
- unique indexes for admission numbers, roll numbers and employee codes

student_guardians is backfilled with one primary row per student from
students.guardian_id when that user belongs to the same school.

The unique indexes fail if live data already has duplicates (for example two
live students in one school with the same admission number). Clean those rows
up before upgrading.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0023"
down_revision: Union[str, None] = "20261021_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("students", sa.Column("status", sa.Integer(), nullable=False, server_default=sa.text("1")))

    op.add_column(
        "staffs",
        sa.Column("employee_type", sa.String(length=16), nullable=False, server_default=sa.text("'teacher'")),
    )
    op.add_column("staffs", sa.Column("employee_code", sa.String(length=32), nullable=True))
    op.add_column("staffs", sa.Column("department", sa.String(length=128), nullable=True))
    op.add_column("staffs", sa.Column("designation", sa.String(length=128), nullable=True))
    op.add_column("staffs", sa.Column("joining_date", sa.Date(), nullable=True))
    op.add_column("staffs", sa.Column("employment_type", sa.String(length=16), nullable=True))

    op.create_index(
        "uq_students_school_admission_no",
        "students",
        ["school_id", "admission_no"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_students_roll_number",
        "students",
        ["school_id", "session_year_id", "class_section_id", "roll_number"],
        unique=True,
        postgresql_where=sa.text("roll_number IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_staffs_school_employee_code",
        "staffs",
        ["school_id", sa.text("upper(employee_code)")],
        unique=True,
        postgresql_where=sa.text("employee_code IS NOT NULL"),
    )

    op.create_table(
        "student_guardians",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("relationship", sa.String(length=16), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "parent_id", name="uq_student_guardians_student_parent"),
    )
    op.create_index("ix_student_guardians_student_id", "student_guardians", ["student_id"])
    op.create_index("ix_student_guardians_parent_id", "student_guardians", ["parent_id"])
    op.create_index("ix_student_guardians_school_id", "student_guardians", ["school_id"])
    op.create_index(
        "uq_student_guardians_primary",
        "student_guardians",
        ["student_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )
    op.execute(
        """
        INSERT INTO student_guardians (student_id, parent_id, relationship, is_primary, school_id, created_at, updated_at)
        SELECT s.id, s.guardian_id, 'Guardian', true, s.school_id, now(), now()
        FROM students s
        JOIN users u ON u.id = s.guardian_id AND u.school_id = s.school_id
        WHERE s.deleted_at IS NULL
        """
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("owner_type", sa.String(length=16), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default=sa.text("'document'")),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_documents_owner", "documents", ["school_id", "owner_type", "owner_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_owner", table_name="documents")
    op.drop_table("documents")

    op.drop_index("uq_student_guardians_primary", table_name="student_guardians")
    op.drop_index("ix_student_guardians_school_id", table_name="student_guardians")
    op.drop_index("ix_student_guardians_parent_id", table_name="student_guardians")
    op.drop_index("ix_student_guardians_student_id", table_name="student_guardians")
    op.drop_table("student_guardians")

    op.drop_index("uq_staffs_school_employee_code", table_name="staffs")
    op.drop_index("uq_students_roll_number", table_name="students")
    op.drop_index("uq_students_school_admission_no", table_name="students")

    for column in ("employment_type", "joining_date", "designation", "department", "employee_code", "employee_type"):
        op.drop_column("staffs", column)
    op.drop_column("students", "status")
