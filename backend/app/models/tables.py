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
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    school_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
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
