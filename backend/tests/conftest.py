from __future__ import annotations
import os
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["DB_CONNECTION"] = "sqlite"
os.environ["SQLITE_DIR"] = str(Path(__file__).resolve().parent / "tmp-data")
os.environ["DB_DATABASE"] = "laravel"
os.environ["SESSION_SECRET"] = "test-secret"
os.environ["ALLOW_DDL"] = "true"
os.environ["APP_ENV"] = "test"

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
    role = Role(name=role_name, guard_name="web", school_id=school_id, created_at=utcnow())
    db.add(role)
    db.flush()
    db.add(ModelHasRole(role_id=role.id, model_type=USER_MODEL, model_id=user_id))


@pytest.fixture()
def client():
    settings = get_settings()
    tmp = Path(settings.sqlite_dir)
    if tmp.exists():
        for path in tmp.glob("*.db"):
            path.unlink()
    reset_engines()
    create_schema()
    create_schema("eschool_demo")
    central = session_factory()()
    school_db = session_factory("eschool_demo")()
    school = School(
        name="Demo School",
        code="DEMO",
        database_name="eschool_demo",
        status=1,
        installed=1,
        created_at=utcnow(),
    )
    central.add(school)
    central.add(SystemSetting(name="web_maintenance", data="0", type="text"))
    central.commit()
    year = SessionYear(
        name="2026",
        default=1,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        school_id=school.id,
        created_at=utcnow(),
    )
    school_db.add(year)
    school_db.flush()
    school_db.add(Section(name="A", school_id=school.id, created_at=utcnow()))
    school_db.flush()
    school_class = SchoolClass(name="Grade 1", medium_id=1, school_id=school.id, created_at=utcnow())
    school_db.add(school_class)
    school_db.flush()
    class_section = ClassSection(
        class_id=school_class.id,
        section_id=1,
        medium_id=1,
        school_id=school.id,
        created_at=utcnow(),
    )
    school_db.add(class_section)
    school_db.flush()
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
    school_db.add_all([student_user, email_student, guardian, teacher])
    school_db.flush()
    school_db.add(
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
    school_db.add(Subject(name="Math", code="M1", medium_id=1, school_id=school.id, created_at=utcnow()))
    school_db.add(
        Attendance(
            class_section_id=1,
            student_id=student_user.id,
            session_year_id=year.id,
            type=1,
            date=date(2026, 4, 2),
            remark="",
            school_id=school.id,
            created_at=utcnow(),
        )
    )
    school_db.add(Exam(name="Midterm", class_id=1, session_year_id=year.id, school_id=school.id, created_at=utcnow()))
    school_db.add(
        Fee(
            name="Tuition",
            due_date=date(2026, 5, 1),
            due_charges=0,
            school_id=school.id,
            session_year_id=year.id,
            created_at=utcnow(),
        )
    )
    school_db.add(Announcement(title="Welcome", description="Hello", session_year_id=year.id, school_id=school.id, created_at=utcnow()))
    school_db.add(
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
    school_db.add(
        Expense(
            title="Books",
            amount=10,
            date=date(2026, 5, 1),
            school_id=school.id,
            session_year_id=year.id,
            created_at=utcnow(),
        )
    )
    assign(school_db, student_user.id, "Student", school.id)
    assign(school_db, email_student.id, "Student", school.id)
    assign(school_db, guardian.id, "Guardian", school.id)
    assign(school_db, teacher.id, "Teacher", school.id)
    school_db.commit()
    central.add(admin)
    central.add(Package(name="Basic", description="Starter", status=1, created_at=utcnow()))
    central.commit()
    central.close()
    school_db.close()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
