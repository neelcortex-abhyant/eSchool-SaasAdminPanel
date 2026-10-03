#!/usr/bin/env python3
"""Build local SQLite mirrors of central + 2 tenants for golden fixture capture without Docker."""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

DATA = ROOT / "datasets" / "sqlite_mirror"
DATA.mkdir(parents=True, exist_ok=True)

os.environ["DB_CONNECTION"] = "sqlite"
os.environ["SQLITE_DIR"] = str(DATA)
os.environ["DB_DATABASE"] = "eschool_central"
os.environ["ALLOW_DDL"] = "true"
os.environ["APP_ENV"] = "local"

from app.core.config import get_settings
from app.core.database import create_schema, reset_engines, session_factory
from app.core.security import hash_password, utcnow
from app.models.tables import (
    USER_MODEL,
    ClassSection,
    ModelHasRole,
    Role,
    School,
    SchoolClass,
    Section,
    SessionYear,
    Student,
    SystemSetting,
    User,
    Package,
)

get_settings.cache_clear()
reset_engines()


def seed_tenant(db_name: str, school_id: int, code: str) -> None:
    create_schema(db_name)
    db = session_factory(db_name)()
    year = SessionYear(
        name="2026",
        default=1,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        school_id=school_id,
        created_at=utcnow(),
    )
    db.add(year)
    db.flush()
    db.add(Section(name="A", school_id=school_id, created_at=utcnow()))
    db.flush()
    klass = SchoolClass(name="Grade 1", medium_id=1, school_id=school_id, created_at=utcnow())
    db.add(klass)
    db.flush()
    cs = ClassSection(class_id=klass.id, section_id=1, medium_id=1, school_id=school_id, created_at=utcnow())
    db.add(cs)
    db.flush()
    pwd = hash_password("secret")
    student = User(
        first_name="Ada",
        last_name="Student",
        email="GR001",
        password=pwd,
        status=1,
        school_id=school_id,
        country_code="+91",
        current_address="12 Demo Street",
        permanent_address="12 Demo Street",
        gender="female",
        created_at=utcnow(),
    )
    guardian = User(
        first_name="Grace",
        last_name="Guardian",
        email="guardian@school.test",
        password=pwd,
        status=1,
        school_id=school_id,
        country_code="+91",
        occupation="Engineer",
        gender="female",
        created_at=utcnow(),
    )
    teacher = User(
        first_name="Tara",
        last_name="Teacher",
        email="teacher@school.test",
        password=pwd,
        status=1,
        school_id=school_id,
        created_at=utcnow(),
    )
    admin = User(
        first_name="Alice",
        last_name="Admin",
        email=f"schooladmin@{code.lower()}.test",
        password=pwd,
        status=1,
        school_id=school_id,
        created_at=utcnow(),
    )
    driver = User(
        first_name="Dan",
        last_name="Driver",
        email=f"driver@{code.lower()}.test",
        password=pwd,
        status=1,
        school_id=school_id,
        created_at=utcnow(),
    )
    db.add_all([student, guardian, teacher, admin, driver])
    db.flush()
    db.add(
        Student(
            user_id=student.id,
            class_section_id=cs.id,
            admission_no="GR001",
            roll_number=1,
            admission_date=date(2026, 4, 1),
            school_id=school_id,
            guardian_id=guardian.id,
            session_year_id=year.id,
            created_at=utcnow(),
        )
    )
    for name, uid in [
        ("Student", student.id),
        ("Guardian", guardian.id),
        ("Teacher", teacher.id),
        ("School Admin", admin.id),
        ("Driver", driver.id),
    ]:
        role = Role(name=name, guard_name="web", school_id=school_id, created_at=utcnow())
        db.add(role)
        db.flush()
        db.add(ModelHasRole(role_id=role.id, model_type=USER_MODEL, model_id=uid))
    db.commit()
    db.close()


def main() -> None:
    for path in DATA.glob("*.db"):
        path.unlink()
    reset_engines()
    create_schema()
    central = session_factory()()
    central.add(
        School(
            name="Demo School A",
            code="DEMOA",
            database_name="eschool_tenant_a",
            status=1,
            installed=1,
            address="100 Demo Ave",
            support_email="admin-a@example.test",
            created_at=utcnow(),
        )
    )
    central.add(
        School(
            name="Demo School B",
            code="DEMOB",
            database_name="eschool_tenant_b",
            status=1,
            installed=1,
            address="200 Demo Ave",
            support_email="admin-b@example.test",
            created_at=utcnow(),
        )
    )
    central.add(SystemSetting(name="web_maintenance", data="0", type="text"))
    central.add(Package(name="Basic", description="Starter", status=1, created_at=utcnow()))
    central.add(
        User(
            first_name="Super",
            last_name="Admin",
            email="admin@eschool.test",
            password=hash_password("secret"),
            status=1,
            created_at=utcnow(),
        )
    )
    central.commit()
    central.close()
    seed_tenant("eschool_tenant_a", 1, "DEMOA")
    seed_tenant("eschool_tenant_b", 2, "DEMOB")
    print("SQLite mirrors ready in", DATA)


if __name__ == "__main__":
    main()
