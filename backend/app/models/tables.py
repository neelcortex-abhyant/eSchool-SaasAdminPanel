from datetime import date as DateType
from datetime import datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

USER_MODEL = "App\\Models\\User"


class TimestampMixin:
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class User(Base, TimestampMixin):
    __tablename__ = "users"

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
    school_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
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
    status: Mapped[int] = mapped_column(Integer, default=1)
    code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    database_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    installed: Mapped[int] = mapped_column(Integer, default=1)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    guard_name: Mapped[str] = mapped_column(String(255), default="web")
    school_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


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
    __tablename__ = "session_years"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    default: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[DateType] = mapped_column(Date)
    end_date: Mapped[DateType] = mapped_column(Date)
    school_id: Mapped[int] = mapped_column(Integer)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Medium(Base, TimestampMixin):
    __tablename__ = "mediums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    school_id: Mapped[int] = mapped_column(Integer)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Section(Base, TimestampMixin):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    school_id: Mapped[int] = mapped_column(Integer)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SchoolClass(Base, TimestampMixin):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    include_semesters: Mapped[int] = mapped_column(Integer, default=0)
    medium_id: Mapped[int] = mapped_column(Integer)
    school_id: Mapped[int] = mapped_column(Integer)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class ClassSection(Base, TimestampMixin):
    __tablename__ = "class_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_id: Mapped[int] = mapped_column(Integer)
    section_id: Mapped[int] = mapped_column(Integer)
    medium_id: Mapped[int] = mapped_column(Integer)
    school_id: Mapped[int] = mapped_column(Integer)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Subject(Base, TimestampMixin):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    bg_color: Mapped[str] = mapped_column(String(32), default="#ffffff")
    image: Mapped[str] = mapped_column(String(512), default="")
    medium_id: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(64), default="Theory")
    school_id: Mapped[int] = mapped_column(Integer)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    class_section_id: Mapped[int] = mapped_column(Integer)
    admission_no: Mapped[str] = mapped_column(String(512))
    roll_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    admission_date: Mapped[DateType] = mapped_column(Date)
    school_id: Mapped[int] = mapped_column(Integer)
    guardian_id: Mapped[int] = mapped_column(Integer)
    session_year_id: Mapped[int] = mapped_column(Integer)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="student")


class Attendance(Base, TimestampMixin):
    __tablename__ = "attendances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_section_id: Mapped[int] = mapped_column(Integer)
    student_id: Mapped[int] = mapped_column(Integer)
    session_year_id: Mapped[int] = mapped_column(Integer)
    type: Mapped[int] = mapped_column(Integer, default=1)
    date: Mapped[DateType] = mapped_column(Date)
    remark: Mapped[str] = mapped_column(String(512), default="")
    school_id: Mapped[int] = mapped_column(Integer)


class Exam(Base, TimestampMixin):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    class_id: Mapped[int] = mapped_column(Integer)
    session_year_id: Mapped[int] = mapped_column(Integer)
    publish: Mapped[int] = mapped_column(Integer, default=0)
    school_id: Mapped[int] = mapped_column(Integer)
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer)
    qualification: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    salary: Mapped[float] = mapped_column(Float, default=0)


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
    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=0)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    data: Mapped[str] = mapped_column(String(255))
    type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class Expense(Base, TimestampMixin):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    amount: Mapped[float] = mapped_column(Float, default=0)
    date: Mapped[DateType] = mapped_column(Date)
    school_id: Mapped[int] = mapped_column(Integer)
    session_year_id: Mapped[int] = mapped_column(Integer)
