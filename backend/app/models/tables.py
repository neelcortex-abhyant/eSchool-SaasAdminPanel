from datetime import date as DateType
from datetime import datetime
from datetime import time as TimeType
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

USER_MODEL = "App\\Models\\User"


class TimestampMixin:
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class User(Base, TimestampMixin):
    """Legacy Laravel-compatible users (integer PK). School-scoped via school_id.

    Distinct from V1 `v1_users` (UUID). Do not merge these tables blindly.
    """

    __tablename__ = "users"
    __table_args__ = (
        # Same email may exist in different schools; globally unique when school_id is set.
        UniqueConstraint("school_id", "email", name="uq_users_school_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(128))
    last_name: Mapped[str] = mapped_column(String(128))
    mobile: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255))
    password: Mapped[str] = mapped_column(String(255))
    gender: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    image: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    dob: Mapped[Optional[DateType]] = mapped_column(Date, nullable=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    current_address: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    permanent_address: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    occupation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1)
    reset_request: Mapped[int] = mapped_column(Integer, default=0)
    fcm_id: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    school_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    two_factor_enabled: Mapped[int] = mapped_column(Integer, default=0)
    two_factor_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    two_factor_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    student: Mapped[Optional["Student"]] = relationship(back_populates="user", uselist=False)


class School(Base, TimestampMixin):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(255), default="")
    support_phone: Mapped[str] = mapped_column(String(255), default="")
    support_email: Mapped[str] = mapped_column(String(255), default="")
    tagline: Mapped[str] = mapped_column(String(255), default="")
    logo: Mapped[str] = mapped_column(String(255), default="")
    admin_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Primary v1 school_admin (UUID). Separate from legacy integer admin_id.
    v1_admin_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[int] = mapped_column(Integer, default=1)
    code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True, index=True)
    # Legacy MySQL physical DB name — kept for import mapping only; not used for connections.
    database_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    installed: Mapped[int] = mapped_column(Integer, default=1)
    # Idempotent provisioning marker (shared Neon; not a physical DB create).
    provisioned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# Non-blank support emails are unique case-insensitively. Blank emails stay allowed
# (column default is "") so existing and future empty values do not collide.
Index(
    "ix_schools_support_email_nonblank",
    func.lower(func.btrim(School.support_email)),
    unique=True,
    postgresql_where=text("btrim(support_email) <> ''"),
)


class Role(Base, TimestampMixin):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("school_id", "name", "guard_name", name="uq_roles_school_name_guard"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    guard_name: Mapped[str] = mapped_column(String(255), default="web")
    school_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("schools.id"), nullable=True, index=True)


class ModelHasRole(Base):
    __tablename__ = "model_has_roles"
    __table_args__ = (UniqueConstraint("role_id", "model_id", "model_type"),)

    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    model_type: Mapped[str] = mapped_column(String(255), primary_key=True)
    model_id: Mapped[int] = mapped_column(Integer, primary_key=True)


class PersonalAccessToken(Base, TimestampMixin):
    __tablename__ = "personal_access_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tokenable_type: Mapped[str] = mapped_column(String(255))
    tokenable_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255))
    token: Mapped[str] = mapped_column(String(64), unique=True)
    abilities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SessionYear(Base, TimestampMixin):
    """School academic year. Soft-deleted rows keep history; names may be reused after delete.

    Uniqueness (active): (school_id, lower(btrim(name))) — migration 0018.
    At most one active default=1 per school — migration 0022.
    Legacy school_id is an integer (no DB FK to schools); tenant checks are app-level.
    """

    __tablename__ = "session_years"
    __table_args__ = (
        Index(
            "uq_session_years_school_name_active",
            "school_id",
            text("lower(btrim(name))"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_session_years_school_default_active",
            "school_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND \"default\" = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    default: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[DateType] = mapped_column(Date)
    end_date: Mapped[DateType] = mapped_column(Date)
    school_id: Mapped[int] = mapped_column(Integer, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Medium(Base, TimestampMixin):
    """Instruction medium (e.g. English). School-scoped; soft-deleteable."""

    __tablename__ = "mediums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    school_id: Mapped[int] = mapped_column(Integer, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Section(Base, TimestampMixin):
    """School-level section name catalog (no class_id). Linked to classes via ClassSection."""

    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    school_id: Mapped[int] = mapped_column(Integer, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SchoolClass(Base, TimestampMixin):
    """School class within a medium. Soft-deleted rows keep history.

    Uniqueness (active): (school_id, medium_id, lower(btrim(name))) — migration 0019.
    medium_id is a legacy integer reference (no DB FK); validated in services.
    """

    __tablename__ = "classes"
    __table_args__ = (
        Index(
            "uq_classes_school_medium_name_active",
            "school_id",
            "medium_id",
            text("lower(btrim(name))"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_classes_medium_id", "medium_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    include_semesters: Mapped[int] = mapped_column(Integer, default=0)
    medium_id: Mapped[int] = mapped_column(Integer)
    school_id: Mapped[int] = mapped_column(Integer, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class ClassSection(Base, TimestampMixin):
    """Maps a school Section onto a SchoolClass (and medium) within one school.

    Uniqueness (active): (school_id, class_id, section_id) — migration 0020.
    class_id / section_id / medium_id are legacy integers (no DB FKs); validated in services.
    """

    __tablename__ = "class_sections"
    __table_args__ = (
        Index(
            "uq_class_sections_school_class_section_active",
            "school_id",
            "class_id",
            "section_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_class_sections_class_id", "class_id"),
        Index("ix_class_sections_section_id", "section_id"),
        Index("ix_class_sections_medium_id", "medium_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_id: Mapped[int] = mapped_column(Integer)
    section_id: Mapped[int] = mapped_column(Integer)
    medium_id: Mapped[int] = mapped_column(Integer)
    school_id: Mapped[int] = mapped_column(Integer, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Subject(Base, TimestampMixin):
    """School subject within a medium. Soft-deleted rows keep history.

    Uniqueness (active non-blank code): (school_id, medium_id, lower(btrim(code))) — migration 0021.
    type values used by API: Theory | Practical (not Compulsory/Elective).
    """

    __tablename__ = "subjects"
    __table_args__ = (
        Index(
            "uq_subjects_school_medium_code_active",
            "school_id",
            "medium_id",
            text("lower(btrim(code))"),
            unique=True,
            postgresql_where=text(
                "deleted_at IS NULL AND code IS NOT NULL AND btrim(code) <> ''"
            ),
        ),
        Index("ix_subjects_medium_id", "medium_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    bg_color: Mapped[str] = mapped_column(String(32), default="#ffffff")
    image: Mapped[str] = mapped_column(String(512), default="")
    medium_id: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(64), default="Theory")
    school_id: Mapped[int] = mapped_column(Integer, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class ClassSubject(Base, TimestampMixin):
    """Maps a subject onto a class within one school. Soft-deleted rows are kept for history."""

    __tablename__ = "class_subjects"
    __table_args__ = (
        Index(
            "uq_class_subjects_school_class_subject_active",
            "school_id",
            "class_id",
            "subject_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    class_id: Mapped[int] = mapped_column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class TeacherAssignment(Base, TimestampMixin):
    """Teacher (Staff) assigned to a subject, optionally for a class-section and session.

    teacher_user_id matches the id returned by GET …/academics/teachers (legacy users.id).
    staff_id is the Staff row for that user in this school.
    """

    __tablename__ = "teacher_assignments"
    __table_args__ = (
        Index(
            "uq_teacher_assignments_active",
            "school_id",
            "staff_id",
            "subject_id",
            "class_section_id",
            "session_year_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staffs.id"), nullable=False, index=True)
    teacher_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    class_section_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("class_sections.id"), nullable=True, index=True
    )
    session_year_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("session_years.id"), nullable=True, index=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class ClassTimetableEntry(Base, TimestampMixin):
    """One class period slot for a school (Module 1). Soft-deleted rows keep history.

    Classroom is deferred (no classroom entity). Working days are Mon–Sat strings.
    """

    __tablename__ = "class_timetable_entries"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_class_timetable_entries_time_order"),
        Index(
            "ix_class_timetable_entries_school_session_cs_day",
            "school_id",
            "session_year_id",
            "class_section_id",
            "day",
        ),
        Index(
            "ix_class_timetable_entries_school_teacher_day",
            "school_id",
            "teacher_user_id",
            "day",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    session_year_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("session_years.id"), nullable=False, index=True
    )
    class_section_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("class_sections.id"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    teacher_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staffs.id"), nullable=False, index=True)
    day: Mapped[str] = mapped_column(String(16), nullable=False)
    start_time: Mapped[TimeType] = mapped_column(Time, nullable=False)
    end_time: Mapped[TimeType] = mapped_column(Time, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Homework(Base, TimestampMixin):
    """School homework / assignment brief (Module 3). Soft-deleted rows keep history.

    Distinct from legacy Laravel ``assignments`` catalog name — new Neon table.
    Attachment metadata is JSON text (validated in services); binary storage optional.
    """

    __tablename__ = "homeworks"
    __table_args__ = (
        CheckConstraint("max_marks IS NULL OR max_marks >= 0", name="ck_homeworks_max_marks"),
        CheckConstraint("allow_late IN (0, 1)", name="ck_homeworks_allow_late"),
        Index(
            "ix_homeworks_school_session_cs",
            "school_id",
            "session_year_id",
            "class_section_id",
        ),
        Index("ix_homeworks_school_teacher", "school_id", "teacher_user_id"),
        Index("ix_homeworks_school_deadline", "school_id", "deadline_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    session_year_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("session_years.id"), nullable=False, index=True
    )
    class_section_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("class_sections.id"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    teacher_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staffs.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_date: Mapped[DateType] = mapped_column(Date, nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    max_marks: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 1 = accept late submissions (status is_late); 0 = reject after deadline.
    allow_late: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    # JSON list of {original_filename, content_type, size_bytes, storage_key?}
    attachments_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class HomeworkSubmission(Base, TimestampMixin):
    """One active submission per student per homework (partial unique index).

    status: submitted | graded. is_late records deadline breach without losing submission.
    """

    __tablename__ = "homework_submissions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted', 'graded')",
            name="ck_homework_submissions_status",
        ),
        CheckConstraint("is_late IN (0, 1)", name="ck_homework_submissions_is_late"),
        CheckConstraint("marks IS NULL OR marks >= 0", name="ck_homework_submissions_marks"),
        Index(
            "uq_homework_submissions_active",
            "homework_id",
            "student_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_homework_submissions_school_homework", "school_id", "homework_id"),
        Index("ix_homework_submissions_school_student", "school_id", "student_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    homework_id: Mapped[int] = mapped_column(Integer, ForeignKey("homeworks.id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    text_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="submitted", server_default="submitted"
    )
    is_late: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    marks: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grade: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # V1 school-admin actor id (UUID string). Not a legacy users.id FK.
    evaluated_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    attachments_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class StudyMaterial(Base, TimestampMixin):
    """Study materials for a class-section/subject (Module 4). Soft-deleted rows keep history.

    resource_type:
    - file: binary via document_storage (storage_key set server-side)
    - video_link / document_reference: validated external https URL only (not fetched)
    chapter/topic are optional free-text metadata (no LessonTopic ORM in Neon).
    """

    __tablename__ = "study_materials"
    __table_args__ = (
        CheckConstraint(
            "resource_type IN ('file', 'video_link', 'document_reference')",
            name="ck_study_materials_resource_type",
        ),
        CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0",
            name="ck_study_materials_size_bytes",
        ),
        Index(
            "ix_study_materials_school_session_cs",
            "school_id",
            "session_year_id",
            "class_section_id",
        ),
        Index("ix_study_materials_school_subject", "school_id", "subject_id"),
        Index("ix_study_materials_school_teacher", "school_id", "teacher_user_id"),
        Index("ix_study_materials_resource_type", "school_id", "resource_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    session_year_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("session_years.id"), nullable=False, index=True
    )
    class_section_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("class_sections.id"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    teacher_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staffs.id"), nullable=False, index=True)
    # V1 school-admin actor who created/last updated the row.
    uploaded_by_v1_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chapter: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    topic: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Server-generated opaque key for resource_type=file; never client-supplied.
    storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Validated https URL for video_link / document_reference.
    external_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class OnlineAssessment(Base, TimestampMixin):
    """MCQ online exam paper (Module 5). Distinct from legacy ``exams`` and Laravel ``online_exams``.

    status: draft | published | closed
    results_published: 0/1 — students see scores/keys only when 1.
    """

    __tablename__ = "online_assessments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'closed')",
            name="ck_online_assessments_status",
        ),
        CheckConstraint("duration_minutes > 0", name="ck_online_assessments_duration"),
        CheckConstraint("total_marks > 0", name="ck_online_assessments_total_marks"),
        CheckConstraint("passing_marks >= 0", name="ck_online_assessments_passing_marks"),
        CheckConstraint(
            "passing_marks <= total_marks",
            name="ck_online_assessments_passing_le_total",
        ),
        CheckConstraint(
            "available_until > available_from",
            name="ck_online_assessments_window",
        ),
        CheckConstraint(
            "results_published IN (0, 1)",
            name="ck_online_assessments_results_published",
        ),
        Index(
            "ix_online_assessments_school_session_cs",
            "school_id",
            "session_year_id",
            "class_section_id",
        ),
        Index("ix_online_assessments_school_subject", "school_id", "subject_id"),
        Index("ix_online_assessments_school_status", "school_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    session_year_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("session_years.id"), nullable=False, index=True
    )
    class_section_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("class_sections.id"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    teacher_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staffs.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_marks: Mapped[float] = mapped_column(Float, nullable=False)
    passing_marks: Mapped[float] = mapped_column(Float, nullable=False)
    available_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    available_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="draft"
    )
    results_published: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class OnlineAssessmentQuestion(Base, TimestampMixin):
    """MCQ question on an assessment. version increments on edit for snapshot integrity."""

    __tablename__ = "online_assessment_questions"
    __table_args__ = (
        CheckConstraint(
            "question_type IN ('mcq')",
            name="ck_online_assessment_questions_type",
        ),
        CheckConstraint("marks > 0", name="ck_online_assessment_questions_marks"),
        CheckConstraint("version >= 1", name="ck_online_assessment_questions_version"),
        Index("ix_online_assessment_questions_assessment", "school_id", "assessment_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    assessment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("online_assessments.id"), nullable=False, index=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    question_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="mcq", server_default="mcq"
    )
    marks: Mapped[float] = mapped_column(Float, nullable=False)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class OnlineAssessmentChoice(Base, TimestampMixin):
    """Answer choice. is_correct must never be serialized to active student attempts."""

    __tablename__ = "online_assessment_choices"
    __table_args__ = (
        CheckConstraint("is_correct IN (0, 1)", name="ck_online_assessment_choices_is_correct"),
        Index("ix_online_assessment_choices_question", "school_id", "question_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("online_assessment_questions.id"), nullable=False, index=True
    )
    choice_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class OnlineAssessmentAttempt(Base, TimestampMixin):
    """One active attempt per student per assessment (partial unique index).

    answer_key_snapshot JSON freezes question versions + correct choice ids at start.
    """

    __tablename__ = "online_assessment_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'submitted', 'expired', 'evaluated')",
            name="ck_online_assessment_attempts_status",
        ),
        CheckConstraint(
            "passed IS NULL OR passed IN (0, 1)",
            name="ck_online_assessment_attempts_passed",
        ),
        Index(
            "uq_online_assessment_attempts_active",
            "assessment_id",
            "student_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_online_assessment_attempts_school_assessment", "school_id", "assessment_id"),
        Index("ix_online_assessment_attempts_school_student", "school_id", "student_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    assessment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("online_assessments.id"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="in_progress", server_default="in_progress"
    )
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    passed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    answer_key_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class OnlineAssessmentAnswer(Base, TimestampMixin):
    """Selected choice for one question on an attempt. choice_id null = unanswered."""

    __tablename__ = "online_assessment_answers"
    __table_args__ = (
        Index(
            "uq_online_assessment_answers_attempt_question",
            "attempt_id",
            "question_id",
            unique=True,
        ),
        Index("ix_online_assessment_answers_school_attempt", "school_id", "attempt_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    attempt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("online_assessment_attempts.id"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("online_assessment_questions.id"), nullable=False, index=True
    )
    choice_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("online_assessment_choices.id"), nullable=True, index=True
    )
    marks_awarded: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Student(Base, TimestampMixin):
    __tablename__ = "students"
    __table_args__ = (
        Index(
            "uq_students_school_admission_no_active",
            "school_id",
            text("lower(btrim(admission_no))"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_students_school_session_cs_roll_active",
            "school_id",
            "session_year_id",
            "class_section_id",
            "roll_number",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND roll_number IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    class_section_id: Mapped[int] = mapped_column(Integer)
    admission_no: Mapped[str] = mapped_column(String(512))
    roll_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    admission_date: Mapped[DateType] = mapped_column(Date)
    school_id: Mapped[int] = mapped_column(Integer)
    guardian_id: Mapped[int] = mapped_column(Integer)
    session_year_id: Mapped[int] = mapped_column(Integer)
    # Module 2/admission: admitted|active|inactive|transferred (migration 0024).
    enrollment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="admitted")
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="student")


class StudentGuardian(Base, TimestampMixin):
    """Multi-guardian association (migration 0025). Legacy students.guardian_id kept in sync by services."""

    __tablename__ = "student_guardians"
    __table_args__ = (
        Index(
            "uq_student_guardians_active_pair",
            "student_id",
            "guardian_user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_student_guardians_one_primary",
            "student_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND is_primary = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    guardian_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False, default="guardian")
    is_primary: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class LegacyUserPasswordToken(Base):
    """Password setup/reset tokens for legacy integer users (migration 0026)."""

    __tablename__ = "legacy_user_password_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Attendance(Base, TimestampMixin):
    __tablename__ = "attendances"
    __table_args__ = (
        Index(
            "uq_attendances_school_session_student_date",
            "school_id",
            "session_year_id",
            "student_id",
            "date",
            unique=True,
        ),
        Index("ix_attendances_school_date", "school_id", "date"),
        Index("ix_attendances_school_class_section_date", "school_id", "class_section_id", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_section_id: Mapped[int] = mapped_column(Integer)
    student_id: Mapped[int] = mapped_column(Integer)
    session_year_id: Mapped[int] = mapped_column(Integer)
    type: Mapped[int] = mapped_column(Integer, default=1)
    date: Mapped[DateType] = mapped_column(Date)
    remark: Mapped[str] = mapped_column(String(512), default="")
    school_id: Mapped[int] = mapped_column(Integer)


class AttendanceLock(Base, TimestampMixin):
    """Persistent attendance locks (migration 0031). Active when unlocked_at IS NULL."""

    __tablename__ = "attendance_locks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    session_year_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    attendance_date: Mapped[DateType] = mapped_column(Date, nullable=False)
    class_section_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    locked_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reason: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    unlocked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    unlocked_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class AttendanceEvent(Base):
    """Absence/leave notification outbox (migration 0031). No delivery worker yet."""

    __tablename__ = "attendance_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    attendance_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    session_year_id: Mapped[int] = mapped_column(Integer, nullable=False)
    attendance_date: Mapped[DateType] = mapped_column(Date, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status_type: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class PersonDocument(Base, TimestampMixin):
    """Private person document metadata (migration 0029; title added in 0037)."""

    __tablename__ = "person_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Exam(Base, TimestampMixin):
    """Offline exam container (legacy academics + Module 6).

    Legacy rows use class_id + publish. Module 6 adds class_section_id, exam_type,
    exam_date and results_processed_at. Subject schedules/marks live in
    offline_exam_* tables (not Laravel exam_timetables / exam_marks names).
    """

    __tablename__ = "exams"
    __table_args__ = (
        Index("ix_exams_school_session", "school_id", "session_year_id"),
        Index("ix_exams_school_class_section", "school_id", "class_section_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    class_id: Mapped[int] = mapped_column(Integer)
    session_year_id: Mapped[int] = mapped_column(Integer)
    # 0 = unpublished (students/parents cannot read results); 1 = published.
    publish: Mapped[int] = mapped_column(Integer, default=0)
    school_id: Mapped[int] = mapped_column(Integer)
    # Module 6 additive fields (nullable for legacy academics rows).
    class_section_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("class_sections.id"), nullable=True, index=True
    )
    exam_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    exam_date: Mapped[Optional[DateType]] = mapped_column(Date, nullable=True)
    results_processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class OfflineExamSchedule(Base, TimestampMixin):
    """Subject-wise schedule under an offline Exam (Module 6)."""

    __tablename__ = "offline_exam_schedules"
    __table_args__ = (
        CheckConstraint("max_marks > 0", name="ck_offline_exam_schedules_max_marks"),
        CheckConstraint("passing_marks >= 0", name="ck_offline_exam_schedules_passing"),
        CheckConstraint(
            "passing_marks <= max_marks",
            name="ck_offline_exam_schedules_passing_le_max",
        ),
        CheckConstraint(
            "end_time IS NULL OR start_time IS NULL OR end_time > start_time",
            name="ck_offline_exam_schedules_time_order",
        ),
        Index(
            "uq_offline_exam_schedules_active",
            "exam_id",
            "class_section_id",
            "subject_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_offline_exam_schedules_school_cs_date",
            "school_id",
            "class_section_id",
            "exam_date",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    exam_id: Mapped[int] = mapped_column(Integer, ForeignKey("exams.id"), nullable=False, index=True)
    session_year_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("session_years.id"), nullable=False, index=True
    )
    class_section_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("class_sections.id"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    teacher_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    staff_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("staffs.id"), nullable=True, index=True
    )
    exam_date: Mapped[DateType] = mapped_column(Date, nullable=False)
    start_time: Mapped[Optional[TimeType]] = mapped_column(Time, nullable=True)
    end_time: Mapped[Optional[TimeType]] = mapped_column(Time, nullable=True)
    max_marks: Mapped[float] = mapped_column(Float, nullable=False)
    passing_marks: Mapped[float] = mapped_column(Float, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class OfflineExamMark(Base, TimestampMixin):
    """Marks for one student on one subject schedule."""

    __tablename__ = "offline_exam_marks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('present', 'absent', 'withheld')",
            name="ck_offline_exam_marks_status",
        ),
        CheckConstraint(
            "marks_obtained IS NULL OR marks_obtained >= 0",
            name="ck_offline_exam_marks_obtained",
        ),
        Index(
            "uq_offline_exam_marks_active",
            "schedule_id",
            "student_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_offline_exam_marks_school_exam", "school_id", "exam_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    exam_id: Mapped[int] = mapped_column(Integer, ForeignKey("exams.id"), nullable=False, index=True)
    schedule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("offline_exam_schedules.id"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    marks_obtained: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="present", server_default="present"
    )
    evaluated_by_v1_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class OfflineExamMarkAudit(Base):
    """Immutable marks correction history (append-only)."""

    __tablename__ = "offline_exam_mark_audits"
    __table_args__ = (
        Index("ix_offline_exam_mark_audits_mark", "school_id", "mark_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    mark_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("offline_exam_marks.id"), nullable=False, index=True
    )
    exam_id: Mapped[int] = mapped_column(Integer, ForeignKey("exams.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False)
    previous_marks: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    new_marks: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    actor_v1_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class OfflineExamResult(Base, TimestampMixin):
    """Processed overall result for one student on one offline exam."""

    __tablename__ = "offline_exam_results"
    __table_args__ = (
        CheckConstraint(
            "passed IS NULL OR passed IN (0, 1)",
            name="ck_offline_exam_results_passed",
        ),
        Index(
            "uq_offline_exam_results_active",
            "exam_id",
            "student_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_offline_exam_results_school_exam", "school_id", "exam_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    exam_id: Mapped[int] = mapped_column(Integer, ForeignKey("exams.id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    total_max_marks: Mapped[float] = mapped_column(
        Float, nullable=False, default=0, server_default="0"
    )
    total_obtained: Mapped[float] = mapped_column(
        Float, nullable=False, default=0, server_default="0"
    )
    percentage: Mapped[float] = mapped_column(
        Float, nullable=False, default=0, server_default="0"
    )
    passed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    subjects_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Fee(Base, TimestampMixin):
    __tablename__ = "fees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    due_date: Mapped[DateType] = mapped_column(Date)
    due_charges: Mapped[float] = mapped_column(Float, default=0)
    school_id: Mapped[int] = mapped_column(Integer)
    session_year_id: Mapped[int] = mapped_column(Integer)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Staff(Base, TimestampMixin):
    __tablename__ = "staffs"
    __table_args__ = (
        Index(
            "uq_staffs_school_employee_id",
            "school_id",
            "employee_id",
            unique=True,
            postgresql_where=text("employee_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    school_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    qualification: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    salary: Mapped[float] = mapped_column(Float, default=0)
    # Module 3 employment fields (migrations 0027–0028).
    employee_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    joining_date: Mapped[Optional[DateType]] = mapped_column(Date, nullable=True)
    employment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    department: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    designation: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class Leave(Base, TimestampMixin):
    __tablename__ = "leaves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(255))
    from_date: Mapped[DateType] = mapped_column(Date)
    to_date: Mapped[DateType] = mapped_column(Date)
    status: Mapped[int] = mapped_column(Integer, default=0)
    school_id: Mapped[int] = mapped_column(Integer)
    session_year_id: Mapped[int] = mapped_column(Integer)


class Announcement(Base, TimestampMixin):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_year_id: Mapped[int] = mapped_column(Integer)
    school_id: Mapped[int] = mapped_column(Integer)


class Package(Base, TimestampMixin):
    """SaaS plan row. Exposed as /api/v1/super-admin/plans (table remains `packages`)."""

    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 0=unpublished/inactive, 1=published/active (legacy + dashboard convention).
    status: Mapped[int] = mapped_column(Integer, default=0)
    # Phase 4 plan fields (additive; subscriptions/features stay later phases).
    monthly_price: Mapped[float] = mapped_column(Float, default=0.0)
    yearly_price: Mapped[float] = mapped_column(Float, default=0.0)
    student_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    staff_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Subscription(Base, TimestampMixin):
    """School ↔ Package subscription (Phase 5). No payment gateway yet."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    package_id: Mapped[int] = mapped_column(Integer, ForeignKey("packages.id"), nullable=False, index=True)
    # 0=inactive, 1=active, 2=expired, 3=cancelled
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)
    start_date: Mapped[DateType] = mapped_column(Date, nullable=False)
    end_date: Mapped[DateType] = mapped_column(Date, nullable=False)
    # monthly | yearly — amount basis for bills (no gateway charge here)
    cycle: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")
    auto_renew: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Price agreed at assignment, or when this row's plan or cycle changes.
    # Null on rows created before the snapshot. Plan edits do not rewrite it.
    # Renewal bills still use the plan price at renewal time.
    agreed_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SubscriptionBill(Base, TimestampMixin):
    """Bill line for a subscription period. Payment collection is a later phase."""

    __tablename__ = "subscription_bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subscriptions.id"), nullable=False, index=True
    )
    # Denormalized for school-scoped queries; must match subscription.school_id.
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 0=pending, 1=paid, 2=overdue, 3=cancelled
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    period_start: Mapped[DateType] = mapped_column(Date, nullable=False)
    period_end: Mapped[DateType] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[DateType]] = mapped_column(Date, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SubscriptionRenewal(Base):
    """Immutable renewal snapshot. Later plan edits do not change these rows."""

    __tablename__ = "subscription_renewals"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "period_start",
            name="uq_subscription_renewals_period",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subscriptions.id"), nullable=False, index=True
    )
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    package_id: Mapped[int] = mapped_column(Integer, ForeignKey("packages.id"), nullable=False, index=True)
    plan_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cycle: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    period_start: Mapped[DateType] = mapped_column(Date, nullable=False)
    period_end: Mapped[DateType] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# 0=created, 1=authorized, 2=captured, 3=failed, 4=refunded.
# A capture marks the bill paid through payment_verification_service, not here.
PAYMENT_STATUS_CREATED = 0
PAYMENT_STATUS_AUTHORIZED = 1
PAYMENT_STATUS_CAPTURED = 2
PAYMENT_STATUS_FAILED = 3
PAYMENT_STATUS_REFUNDED = 4


class PaymentTransaction(Base, TimestampMixin):
    """Gateway order for one subscription bill. Amount is integer paise.

    One row per gateway order. gateway_payment_id stays null until the
    gateway reports a payment. Secrets and webhook signatures are not stored.
    A bill has at most one row that is not refunded, so it has at most one
    payable order and at most one captured payment.
    """

    __tablename__ = "payment_transactions"
    __table_args__ = (
        Index(
            "uq_payment_transactions_bill_open",
            "bill_id",
            unique=True,
            postgresql_where=text("status <> 4"),
        ),
        UniqueConstraint("gateway_order_id", name="uq_payment_transactions_gateway_order_id"),
        UniqueConstraint("gateway_payment_id", name="uq_payment_transactions_gateway_payment_id"),
        UniqueConstraint(
            "school_id",
            "idempotency_key",
            name="uq_payment_transactions_school_idempotency",
        ),
        CheckConstraint("amount_paise >= 0", name="ck_payment_transactions_amount_paise_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bill_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subscription_bills.id"), nullable=False, index=True
    )
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    gateway_order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    gateway_payment_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=PAYMENT_STATUS_CREATED, index=True)


class PaymentWebhookEvent(Base):
    """Processed gateway webhook identity. Duplicate deliveries hit the unique key.

    The gateway ids, amount, currency, and outcome are kept for diagnosis.
    The raw payload and signature are not stored.
    """

    __tablename__ = "payment_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "event_id",
            name="uq_payment_webhook_events_provider_event",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="razorpay")
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payment_transaction_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("payment_transactions.id"), nullable=True, index=True
    )
    gateway_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    gateway_payment_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    amount_paise: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SubscriptionInvoice(Base):
    """Issued subscription receipt. Rows are not updated after insert.

    A correction or refund needs a separate credit note that references
    invoice_number. This table has no update path. Tax columns stay null
    until a tax configuration exists; null is not a zero-rate tax.
    """

    __tablename__ = "subscription_invoices"
    __table_args__ = (
        UniqueConstraint("invoice_number", name="uq_subscription_invoices_number"),
        UniqueConstraint("payment_transaction_id", name="uq_subscription_invoices_payment"),
        CheckConstraint("amount_paise >= 0", name="ck_subscription_invoices_amount_non_negative"),
        CheckConstraint("total_amount_paise >= 0", name="ck_subscription_invoices_total_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(32), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    payment_transaction_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("payment_transactions.id"), nullable=False
    )
    bill_id: Mapped[int] = mapped_column(Integer, ForeignKey("subscription_bills.id"), nullable=False, index=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    subscription_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subscriptions.id"), nullable=False, index=True
    )
    package_id: Mapped[int] = mapped_column(Integer, ForeignKey("packages.id"), nullable=False)
    gateway: Mapped[str] = mapped_column(String(32), nullable=False)
    gateway_order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    gateway_payment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_label: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    tax_rate_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    tax_amount_paise: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    total_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    school_name: Mapped[str] = mapped_column(String(255), nullable=False)
    school_address: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    school_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    school_phone: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    plan_name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cycle: Mapped[str] = mapped_column(String(16), nullable=False)
    period_start: Mapped[DateType] = mapped_column(Date, nullable=False)
    period_end: Mapped[DateType] = mapped_column(Date, nullable=False)


class SubscriptionInvoiceCounter(Base):
    """Per-year sequence for SUB-YYYY-NNNNNN. Locked with FOR UPDATE."""

    __tablename__ = "subscription_invoice_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)


class Addon(Base, TimestampMixin):
    """Catalog add-on (Phase 6). Assigned to schools via addon_subscriptions."""

    __tablename__ = "addons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 0=inactive/unpublished, 1=active
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AddonSubscription(Base, TimestampMixin):
    """School assignment of an add-on onto a subscription (Phase 6)."""

    __tablename__ = "addon_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    addon_id: Mapped[int] = mapped_column(Integer, ForeignKey("addons.id"), nullable=False, index=True)
    subscription_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subscriptions.id"), nullable=False, index=True
    )
    # 0=inactive, 1=active
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)
    start_date: Mapped[Optional[DateType]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[DateType]] = mapped_column(Date, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    data: Mapped[str] = mapped_column(String(255))
    type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class AuditLog(Base):
    """Immutable Super Admin action log (Phase 8). No update/delete APIs."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    school_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class Notification(Base, TimestampMixin):
    """Platform notification record (Phase 8). No email/SMS/push delivery."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 0=draft, 1=active/published, 2=archived
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    school_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("schools.id"), nullable=True, index=True
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Expense(Base, TimestampMixin):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    amount: Mapped[float] = mapped_column(Float, default=0)
    date: Mapped[DateType] = mapped_column(Date)
    school_id: Mapped[int] = mapped_column(Integer)
    session_year_id: Mapped[int] = mapped_column(Integer)
