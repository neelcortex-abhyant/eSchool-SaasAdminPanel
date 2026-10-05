from __future__ import annotations

import os
from datetime import date

import pytest
from fastapi.testclient import TestClient

from tests.pg_test_utils import ensure_postgres_database, resolve_test_database_url, wipe_public_schema

# Configure isolated Postgres BEFORE importing app settings.
_TEST_URL = resolve_test_database_url()
os.environ["TEST_DATABASE_URL"] = _TEST_URL
os.environ["NEON_DATABASE_URL"] = _TEST_URL  # app uses a single URL; point it at the test DB
os.environ["SESSION_SECRET"] = "test-secret"
os.environ["ALLOW_DDL"] = "true"
os.environ["APP_ENV"] = "test"
os.environ["V1_SESSION_TTL_MINUTES"] = "10080"

ensure_postgres_database(_TEST_URL)
wipe_public_schema(_TEST_URL)

from app.core.config import get_settings
from app.core.database import create_schema, reset_engines, session_factory
from app.core.security import hash_password, utcnow
from app.models.tables import (
    USER_MODEL,
    Announcement,
    Attendance,
    ClassSection,
    Exam,
    Expense,
    Fee,
    Leave,
    ModelHasRole,
    Package,
    Role,
    School,
    SchoolClass,
    Section,
    SessionYear,
    Student,
    Subject,
    SystemSetting,
    User,
)

get_settings.cache_clear()
reset_engines()


def assign(db, user_id, role_name, school_id):
    from sqlalchemy import select

    role = db.scalar(
        select(Role).where(
            Role.name == role_name,
            Role.guard_name == "web",
            Role.school_id == school_id,
        )
    )
    if role is None:
        role = Role(name=role_name, guard_name="web", school_id=school_id, created_at=utcnow())
        db.add(role)
        db.flush()
    db.add(ModelHasRole(role_id=role.id, model_type=USER_MODEL, model_id=user_id))


def _seed_school(db, *, name: str, code: str) -> School:
    school = School(
        name=name,
        code=code,
        database_name=f"legacy_{code.lower()}",  # import mapping only
        status=1,
        installed=1,
        created_at=utcnow(),
    )
    db.add(school)
    db.flush()
    return school


@pytest.fixture()
def client():
    get_settings.cache_clear()
    reset_engines()
    wipe_public_schema(_TEST_URL)
    create_schema()

    db = session_factory()()
    school = _seed_school(db, name="Demo School", code="DEMO")
    other = _seed_school(db, name="Other School", code="OTHER")
    db.add(SystemSetting(name="web_maintenance", data="0", type="text"))
    year = SessionYear(
        name="2026",
        default=1,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        school_id=school.id,
        created_at=utcnow(),
    )
    db.add(year)
    db.flush()
    section = Section(name="A", school_id=school.id, created_at=utcnow())
    db.add(section)
    db.flush()
    school_class = SchoolClass(name="Grade 1", medium_id=1, school_id=school.id, created_at=utcnow())
    db.add(school_class)
    db.flush()
    class_section = ClassSection(
        class_id=school_class.id,
        section_id=section.id,
        medium_id=1,
        school_id=school.id,
        created_at=utcnow(),
    )
    db.add(class_section)
    db.flush()

    student_user = User(
        first_name="Ada",
        last_name="Student",
        email="GR001",
        password=hash_password("secret"),
        status=1,
        school_id=school.id,
        country_code="+91",
        current_address="12 Demo Street",
        permanent_address="12 Demo Street",
        occupation=None,
        gender="female",
        created_at=utcnow(),
    )
    email_student = User(
        first_name="Sam",
        last_name="Student",
        email="student@school.test",
        password=hash_password("secret"),
        status=1,
        school_id=school.id,
        created_at=utcnow(),
    )
    # Same email in another school — must not authenticate against DEMO.
    other_student = User(
        first_name="Other",
        last_name="Student",
        email="GR001",
        password=hash_password("other-secret"),
        status=1,
        school_id=other.id,
        created_at=utcnow(),
    )
    guardian = User(
        first_name="Grace",
        last_name="Guardian",
        email="guardian@school.test",
        password=hash_password("secret"),
        status=1,
        school_id=school.id,
        created_at=utcnow(),
    )
    teacher = User(
        first_name="Tara",
        last_name="Teacher",
        email="teacher@school.test",
        password=hash_password("secret"),
        status=1,
        school_id=school.id,
        created_at=utcnow(),
    )
    admin = User(
        first_name="Super",
        last_name="Admin",
        email="admin@eschool.test",
        mobile="9000000000",
        password=hash_password("secret"),
        status=1,
        school_id=None,
        created_at=utcnow(),
    )
    db.add_all([student_user, email_student, other_student, guardian, teacher, admin])
    db.flush()
    db.add(
        Student(
            user_id=student_user.id,
            class_section_id=class_section.id,
            admission_no="GR001",
            roll_number=1,
            admission_date=date(2026, 4, 1),
            school_id=school.id,
            guardian_id=guardian.id,
            session_year_id=year.id,
            created_at=utcnow(),
        )
    )
    other_year = SessionYear(
        name="2026-O",
        default=1,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        school_id=other.id,
        created_at=utcnow(),
    )
    db.add(other_year)
    db.flush()
    db.add(
        Student(
            user_id=other_student.id,
            class_section_id=class_section.id,
            admission_no="GR001",
            roll_number=1,
            admission_date=date(2026, 4, 1),
            school_id=other.id,
            guardian_id=guardian.id,
            session_year_id=other_year.id,
            created_at=utcnow(),
        )
    )
    db.add(Subject(name="Math", code="M1", medium_id=1, school_id=school.id, created_at=utcnow()))
    db.add(
        Attendance(
            class_section_id=class_section.id,
            student_id=student_user.id,
            session_year_id=year.id,
            type=1,
            date=date(2026, 4, 2),
            remark="",
            school_id=school.id,
            created_at=utcnow(),
        )
    )
    db.add(Exam(name="Midterm", class_id=school_class.id, session_year_id=year.id, school_id=school.id, created_at=utcnow()))
    db.add(
        Fee(
            name="Tuition",
            due_date=date(2026, 5, 1),
            due_charges=0,
            school_id=school.id,
            session_year_id=year.id,
            created_at=utcnow(),
        )
    )
    db.add(
        Announcement(
            title="Welcome",
            description="Hello",
            session_year_id=year.id,
            school_id=school.id,
            created_at=utcnow(),
        )
    )
    db.add(
        Leave(
            user_id=teacher.id,
            reason="Trip",
            from_date=date(2026, 5, 1),
            to_date=date(2026, 5, 2),
            school_id=school.id,
            session_year_id=year.id,
            created_at=utcnow(),
        )
    )
    db.add(
        Expense(
            title="Books",
            amount=10,
            date=date(2026, 5, 1),
            school_id=school.id,
            session_year_id=year.id,
            created_at=utcnow(),
        )
    )
    assign(db, student_user.id, "Student", school.id)
    assign(db, email_student.id, "Student", school.id)
    assign(db, guardian.id, "Guardian", school.id)
    assign(db, teacher.id, "Teacher", school.id)
    db.add(Package(name="Basic", description="Starter", status=1, created_at=utcnow()))
    db.commit()
    db.close()

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    reset_engines()
