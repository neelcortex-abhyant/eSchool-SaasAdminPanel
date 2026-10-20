"""School Admin roles and permissions.

Permission keys and role definitions live here (code catalog). Which roles a
school_admin holds is stored in v1_user_roles. A school_admin with no rows
holds DEFAULT_ADMIN_ROLE, so accounts created before RBAC keep full access.

super_admin is a platform role on v1_users.role and is never in this catalog,
so it can never be granted through role assignment.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.v1.admin_role import UserAdminRole
from app.models.v1.roles import ROLE_SCHOOL_ADMIN
from app.models.v1.user import User

PERM_DASHBOARD = "dashboard.view"
PERM_SCHOOL = "school.manage"
PERM_STUDENTS = "students.manage"
PERM_TEACHERS = "teachers.manage"
PERM_FEES = "fees.manage"
PERM_EXAMS = "exams.manage"
PERM_ATTENDANCE = "attendance.manage"
PERM_REPORTS = "reports.view"
PERM_SETTINGS = "settings.manage"

# Ordered: responses list permissions in this order.
PERMISSIONS: dict[str, str] = {
    PERM_DASHBOARD: "Dashboard",
    PERM_SCHOOL: "School Management",
    PERM_STUDENTS: "Student Management",
    PERM_TEACHERS: "Teacher Management",
    PERM_FEES: "Fees",
    PERM_EXAMS: "Exams",
    PERM_ATTENDANCE: "Attendance",
    PERM_REPORTS: "Reports",
    PERM_SETTINGS: "Settings",
}

ADMIN_ROLE_SCHOOL = "school_admin"
ADMIN_ROLE_ACADEMIC = "academic_admin"
ADMIN_ROLE_ACCOUNTS = "accounts_admin"
DEFAULT_ADMIN_ROLE = ADMIN_ROLE_SCHOOL

# Ordered: responses list roles in this order.
ADMIN_ROLES: dict[str, dict] = {
    ADMIN_ROLE_SCHOOL: {
        "label": "School Admin",
        "permissions": tuple(PERMISSIONS),
    },
    ADMIN_ROLE_ACADEMIC: {
        "label": "Academic Admin",
        "permissions": (
            PERM_DASHBOARD,
            PERM_STUDENTS,
            PERM_TEACHERS,
            PERM_EXAMS,
            PERM_ATTENDANCE,
            PERM_REPORTS,
        ),
    },
    ADMIN_ROLE_ACCOUNTS: {
        "label": "Accounts Admin",
        "permissions": (PERM_DASHBOARD, PERM_FEES, PERM_REPORTS),
    },
}


class RbacError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def role_catalog() -> list[dict]:
    return [
        {"key": key, "label": role["label"], "permissions": list(role["permissions"])}
        for key, role in ADMIN_ROLES.items()
    ]


def permission_catalog() -> list[dict]:
    return [{"key": key, "label": label} for key, label in PERMISSIONS.items()]


def normalize_roles(roles: list[str]) -> list[str]:
    """Validate requested role keys; return them de-duplicated in catalog order."""
    requested = {r.strip() for r in roles}
    if not requested:
        raise RbacError("At least one role is required", status_code=422)
    unknown = sorted(requested - set(ADMIN_ROLES))
    if unknown:
        raise RbacError(f"Unknown role: {', '.join(unknown)}", status_code=422)
    return [key for key in ADMIN_ROLES if key in requested]


def effective_roles(db: Session, user: User) -> list[str]:
    if user.role != ROLE_SCHOOL_ADMIN:
        return []
    stored = set(db.scalars(select(UserAdminRole.role).where(UserAdminRole.user_id == user.id)))
    # Ignore keys removed from the catalog; fall back to the default if nothing is left.
    roles = [key for key in ADMIN_ROLES if key in stored]
    return roles or [DEFAULT_ADMIN_ROLE]


def permissions_for_roles(roles: list[str]) -> list[str]:
    granted = {perm for key in roles for perm in ADMIN_ROLES.get(key, {}).get("permissions", ())}
    return [perm for perm in PERMISSIONS if perm in granted]


def permissions_for(db: Session, user: User) -> list[str]:
    return permissions_for_roles(effective_roles(db, user))


def set_roles(db: Session, user: User, roles: list[str]) -> tuple[list[str], list[str]]:
    """Replace the user's roles. Does not commit. Returns (previous, new)."""
    if user.role != ROLE_SCHOOL_ADMIN:
        raise RbacError("Roles can only be assigned to school admins", status_code=422)
    new_roles = normalize_roles(roles)
    previous = effective_roles(db, user)
    db.execute(delete(UserAdminRole).where(UserAdminRole.user_id == user.id))
    db.add_all([UserAdminRole(user_id=user.id, role=key) for key in new_roles])
    db.flush()
    return previous, new_roles
