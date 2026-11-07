"""School branch CRUD + v1 UUID branch ACL (never trust X-Branch-Id alone)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import School, SchoolBranch, Staff, Student
from app.models.v1.branch_access import UserBranchAccess
from app.models.v1.user import User
from app.services.v1 import rbac


class BranchError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class BranchContext:
    school_id: int
    branch_id: int
    allowed_branch_ids: tuple[int, ...]
    is_full_school_admin: bool


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _branch_item(row: SchoolBranch) -> dict:
    return {
        "id": row.id,
        "school_id": row.school_id,
        "name": row.name,
        "code": row.code,
        "address": row.address or "",
        "status": row.status,
        "is_default": bool(row.is_default),
        "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None,
    }


def ensure_default_branch(db: Session, school_id: int) -> SchoolBranch:
    """Idempotent: return existing active branch, else create Main default."""
    existing = db.scalars(
        select(SchoolBranch).where(
            SchoolBranch.school_id == school_id,
            SchoolBranch.deleted_at.is_(None),
        )
    ).first()
    if existing is not None:
        return existing
    school = db.get(School, school_id)
    if school is None or school.deleted_at is not None:
        raise BranchError(404, "School not found")
    row = SchoolBranch(
        school_id=school_id,
        name="Main",
        code="MAIN",
        address="",
        status=1,
        is_default=1,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.flush()
    return row


def list_branches(db: Session, school_id: int, *, include_disabled: bool = False) -> list[dict]:
    ensure_default_branch(db, school_id)
    q = select(SchoolBranch).where(
        SchoolBranch.school_id == school_id,
        SchoolBranch.deleted_at.is_(None),
    )
    if not include_disabled:
        q = q.where(SchoolBranch.status == 1)
    rows = db.scalars(q.order_by(SchoolBranch.is_default.desc(), SchoolBranch.id.asc())).all()
    return [_branch_item(r) for r in rows]


def get_branch(db: Session, school_id: int, branch_id: int) -> dict:
    row = _owned_branch(db, school_id, branch_id, allow_disabled=True)
    return _branch_item(row)


def _lock_school(db: Session, school_id: int) -> School:
    """Row-lock the school so quota checks and inserts share one transaction."""
    school = db.execute(
        select(School).where(School.id == school_id).with_for_update()
    ).scalar_one_or_none()
    if school is None or school.deleted_at is not None:
        raise BranchError(404, "School not found")
    return school


def active_branch_count(db: Session, school_id: int) -> int:
    """Active, non-deleted branches. Inactive or soft-deleted rows do not consume quota."""
    value = db.scalar(
        select(func.count())
        .select_from(SchoolBranch)
        .where(
            SchoolBranch.school_id == school_id,
            SchoolBranch.deleted_at.is_(None),
            SchoolBranch.status == 1,
        )
    )
    return int(value or 0)


def _quota_fields(school: School) -> tuple[bool, int]:
    enabled = bool(getattr(school, "branch_creation_enabled", False))
    limit = int(getattr(school, "max_branches", 1) or 1)
    return enabled, limit


def _provision_main_if_missing(db: Session, school_id: int) -> None:
    """Internal only. Flush a default Main branch when the school has none.

    Does not check Super Admin permission and does not commit. Additional
    branch creation still has to pass the quota check in the same transaction.
    """
    existing = db.scalars(
        select(SchoolBranch.id).where(
            SchoolBranch.school_id == school_id,
            SchoolBranch.deleted_at.is_(None),
        )
    ).first()
    if existing is not None:
        return
    now = _now()
    db.add(
        SchoolBranch(
            school_id=school_id,
            name="Main",
            code="MAIN",
            address="",
            status=1,
            is_default=1,
            created_at=now,
            updated_at=now,
        )
    )
    db.flush()


def _branch_people_counts(db: Session, school_id: int) -> dict[int, dict[str, int]]:
    """Student rows (not soft-deleted) and staff rows per branch. Staff is the teacher proxy."""
    counts: dict[int, dict[str, int]] = {}
    student_rows = db.execute(
        select(Student.branch_id, func.count())
        .where(Student.school_id == school_id, Student.deleted_at.is_(None))
        .group_by(Student.branch_id)
    ).all()
    for branch_id, total in student_rows:
        if branch_id is None:
            continue
        counts.setdefault(int(branch_id), {"student_count": 0, "teacher_count": 0})
        counts[int(branch_id)]["student_count"] = int(total or 0)
    staff_rows = db.execute(
        select(Staff.branch_id, func.count())
        .where(Staff.school_id == school_id)
        .group_by(Staff.branch_id)
    ).all()
    for branch_id, total in staff_rows:
        if branch_id is None:
            continue
        counts.setdefault(int(branch_id), {"student_count": 0, "teacher_count": 0})
        counts[int(branch_id)]["teacher_count"] = int(total or 0)
    return counts


def school_branch_summary(db: Session, school_id: int) -> dict:
    school = db.get(School, school_id)
    if school is None or school.deleted_at is not None:
        raise BranchError(404, "School not found")
    rows = db.scalars(
        select(SchoolBranch)
        .where(SchoolBranch.school_id == school_id, SchoolBranch.deleted_at.is_(None))
        .order_by(SchoolBranch.is_default.desc(), SchoolBranch.id.asc())
    ).all()
    enabled, limit = _quota_fields(school)
    active = sum(1 for row in rows if row.status == 1)
    inactive = len(rows) - active
    people = _branch_people_counts(db, school_id)
    items = []
    for row in rows:
        extra = people.get(row.id, {"student_count": 0, "teacher_count": 0})
        items.append(
            {
                **_branch_item(row),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "student_count": extra["student_count"],
                "teacher_count": extra["teacher_count"],
            }
        )
    return {
        "school_id": school.id,
        "school_name": school.name,
        "total_branches": len(rows),
        "active_branches": active,
        "inactive_branches": inactive,
        "max_branches": limit,
        "remaining_capacity": max(0, limit - active),
        "branch_creation_enabled": enabled,
        "branches": items,
    }


def update_branch_settings(
    db: Session,
    school_id: int,
    *,
    max_branches: int,
    branch_creation_enabled: bool,
) -> dict:
    """Super Admin only (enforced at the route). Does not delete or deactivate branches."""
    if int(max_branches) < 1:
        raise BranchError(422, "max_branches must be at least 1")
    school = _lock_school(db, school_id)
    active = active_branch_count(db, school_id)
    if int(max_branches) < active:
        db.rollback()
        raise BranchError(
            422,
            "max_branches cannot be lower than the current number of active branches",
        )
    school.max_branches = int(max_branches)
    school.branch_creation_enabled = bool(branch_creation_enabled)
    school.updated_at = _now()
    db.commit()
    return school_branch_summary(db, school_id)


def create_branch(
    db: Session,
    school_id: int,
    *,
    name: str,
    code: str | None = None,
    address: str = "",
) -> dict:
    """Create an additional branch. Quota is checked under a school row lock."""
    cleaned = (name or "").strip()
    if not cleaned:
        raise BranchError(422, "Branch name is required")
    if len(cleaned) > 255:
        raise BranchError(422, "Branch name must be at most 255 characters")
    code_clean = (code or "").strip() or None
    if code_clean and len(code_clean) > 64:
        raise BranchError(422, "Branch code must be at most 64 characters")
    try:
        school = _lock_school(db, school_id)
        _provision_main_if_missing(db, school_id)
        enabled, limit = _quota_fields(school)
        if not enabled:
            db.rollback()
            raise BranchError(403, "Branch creation is not enabled for this school")
        active = active_branch_count(db, school_id)
        if active >= limit:
            db.rollback()
            raise BranchError(403, "Branch limit reached")
        clash = db.scalars(
            select(SchoolBranch).where(
                SchoolBranch.school_id == school_id,
                SchoolBranch.deleted_at.is_(None),
            )
        ).all()
        for row in clash:
            if row.name.strip().lower() == cleaned.lower():
                db.rollback()
                raise BranchError(409, "A branch with this name already exists")
        row = SchoolBranch(
            school_id=school_id,
            name=cleaned,
            code=code_clean,
            address=(address or "")[:512],
            status=1,
            is_default=0,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _branch_item(row)
    except BranchError:
        raise
    except Exception:
        db.rollback()
        raise


def update_branch(db: Session, school_id: int, branch_id: int, body: dict) -> dict:
    row = _owned_branch(db, school_id, branch_id, allow_disabled=True)
    if "name" in body and body["name"] is not None:
        cleaned = str(body["name"]).strip()
        if not cleaned:
            raise BranchError(422, "Branch name is required")
        for other in db.scalars(
            select(SchoolBranch).where(
                SchoolBranch.school_id == school_id,
                SchoolBranch.deleted_at.is_(None),
                SchoolBranch.id != row.id,
            )
        ).all():
            if other.name.strip().lower() == cleaned.lower():
                raise BranchError(409, "A branch with this name already exists")
        row.name = cleaned
    if "code" in body:
        code_clean = (str(body["code"]).strip() if body["code"] is not None else "") or None
        row.code = code_clean
    if "address" in body and body["address"] is not None:
        row.address = str(body["address"])[:512]
    if "status" in body and body["status"] is not None:
        status = int(body["status"])
        if status not in (0, 1):
            raise BranchError(422, "status must be 0 or 1")
        if status == 0 and row.is_default == 1:
            raise BranchError(422, "Cannot disable the default branch")
        row.status = status
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return _branch_item(row)


def soft_delete_branch(db: Session, school_id: int, branch_id: int) -> dict:
    row = _owned_branch(db, school_id, branch_id, allow_disabled=True)
    if row.is_default == 1:
        raise BranchError(422, "Cannot delete the default branch")
    row.deleted_at = _now()
    row.status = 0
    row.updated_at = _now()
    db.commit()
    return {"id": branch_id, "deleted": True}


def set_branch_admins(
    db: Session,
    school_id: int,
    branch_id: int,
    user_ids: list[uuid.UUID],
) -> dict:
    """Replace v1_user_branch_access for this branch (UUID identity only)."""
    branch = _owned_branch(db, school_id, branch_id, allow_disabled=True)
    unique_ids = list(dict.fromkeys(user_ids))
    users: list[User] = []
    for uid in unique_ids:
        user = db.get(User, uid)
        if user is None:
            raise BranchError(404, f"User {uid} not found")
        if user.school_id != school_id:
            raise BranchError(422, "User does not belong to this school")
        users.append(user)

    existing = db.scalars(
        select(UserBranchAccess).where(UserBranchAccess.branch_id == branch.id)
    ).all()
    for row in existing:
        db.delete(row)
    db.flush()
    for user in users:
        db.add(
            UserBranchAccess(
                user_id=user.id,
                branch_id=branch.id,
                access_role="branch_admin",
            )
        )
        # Ensure catalog role includes branch_admin when assigning ACL.
        roles = rbac.effective_roles(db, user)
        if rbac.ADMIN_ROLE_BRANCH not in roles and rbac.ADMIN_ROLE_SCHOOL not in roles:
            rbac.set_roles(db, user, roles + [rbac.ADMIN_ROLE_BRANCH])
    db.commit()
    return {
        "branch_id": branch.id,
        "user_ids": [str(u.id) for u in users],
    }


def list_branch_admins(db: Session, school_id: int, branch_id: int) -> list[dict]:
    branch = _owned_branch(db, school_id, branch_id, allow_disabled=True)
    rows = db.scalars(
        select(UserBranchAccess).where(UserBranchAccess.branch_id == branch.id)
    ).all()
    items = []
    for row in rows:
        user = db.get(User, row.user_id)
        if user is None:
            continue
        items.append(
            {
                "user_id": str(row.user_id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "access_role": row.access_role,
            }
        )
    return items


def allowed_branch_ids_for_user(db: Session, user: User) -> tuple[list[int], bool]:
    """Return (allowed_ids, is_full_school_admin)."""
    if user.school_id is None:
        return [], False
    ensure_default_branch(db, user.school_id)
    roles = rbac.effective_roles(db, user)
    is_full = rbac.ADMIN_ROLE_SCHOOL in roles
    all_active = db.scalars(
        select(SchoolBranch.id).where(
            SchoolBranch.school_id == user.school_id,
            SchoolBranch.deleted_at.is_(None),
            SchoolBranch.status == 1,
        )
    ).all()
    if is_full:
        return list(all_active), True
    granted = set(
        db.scalars(
            select(UserBranchAccess.branch_id).where(UserBranchAccess.user_id == user.id)
        ).all()
    )
    allowed = [bid for bid in all_active if bid in granted]
    return allowed, False


def resolve_branch_context(
    db: Session,
    user: User,
    *,
    header_branch_id: int | None,
    allow_consolidated: bool = False,
) -> BranchContext:
    """Clarification 3 pipeline. header_branch_id is a hint only."""
    if user.school_id is None:
        raise BranchError(403, "No school assigned")
    school_id = int(user.school_id)
    allowed, is_full = allowed_branch_ids_for_user(db, user)
    if not allowed:
        raise BranchError(403, "No branch access")

    if header_branch_id is None:
        if allow_consolidated and is_full:
            # Special: branch_id=0 means consolidated across allowed set.
            return BranchContext(
                school_id=school_id,
                branch_id=0,
                allowed_branch_ids=tuple(allowed),
                is_full_school_admin=is_full,
            )
        default = db.scalars(
            select(SchoolBranch).where(
                SchoolBranch.school_id == school_id,
                SchoolBranch.is_default == 1,
                SchoolBranch.deleted_at.is_(None),
                SchoolBranch.status == 1,
            )
        ).first()
        if default is None:
            default = ensure_default_branch(db, school_id)
        if default.id not in allowed:
            # Branch admin without default — use first allowed.
            if not is_full:
                header_branch_id = allowed[0]
            else:
                raise BranchError(403, "Default branch not accessible")
        else:
            header_branch_id = default.id

    branch = db.get(SchoolBranch, int(header_branch_id))
    if branch is None or branch.deleted_at is not None:
        raise BranchError(404, "Branch not found")
    if branch.school_id != school_id:
        raise BranchError(403, "Branch does not belong to this school")
    if branch.status != 1:
        raise BranchError(403, "Branch is disabled")
    if branch.id not in allowed:
        raise BranchError(403, "Not authorized for this branch")

    return BranchContext(
        school_id=school_id,
        branch_id=branch.id,
        allowed_branch_ids=tuple(allowed),
        is_full_school_admin=is_full,
    )


def assert_same_branch(row_school_id: int | None, row_branch_id: int | None, ctx: BranchContext) -> None:
    if row_school_id != ctx.school_id:
        raise BranchError(404, "Resource not found")
    if ctx.branch_id == 0:
        if row_branch_id not in ctx.allowed_branch_ids:
            raise BranchError(404, "Resource not found")
        return
    if row_branch_id != ctx.branch_id:
        raise BranchError(404, "Resource not found")


def _owned_branch(
    db: Session, school_id: int, branch_id: int, *, allow_disabled: bool = False
) -> SchoolBranch:
    row = db.get(SchoolBranch, branch_id)
    if row is None or row.deleted_at is not None or row.school_id != school_id:
        raise BranchError(404, "Branch not found")
    if not allow_disabled and row.status != 1:
        raise BranchError(404, "Branch not found")
    return row


def me_branches_payload(db: Session, user: User, *, active_branch_id: int | None = None) -> dict:
    allowed, is_full = allowed_branch_ids_for_user(db, user)
    items = []
    default_id = None
    for bid in allowed:
        row = db.get(SchoolBranch, bid)
        if row is None:
            continue
        items.append(_branch_item(row))
        if row.is_default == 1:
            default_id = row.id
    if default_id is None and items:
        default_id = items[0]["id"]
    active = active_branch_id
    if active is not None and active not in allowed:
        active = None
    school = db.scalars(select(School).where(School.id == int(user.school_id))).first()
    try:
        enabled, limit = _quota_fields(school) if school is not None else (False, 1)
        active_count = active_branch_count(db, int(user.school_id))
        total_count = int(
            db.scalar(
                select(func.count())
                .select_from(SchoolBranch)
                .where(
                    SchoolBranch.school_id == int(user.school_id),
                    SchoolBranch.deleted_at.is_(None),
                )
            )
            or 0
        )
    except (TypeError, ValueError):
        enabled, limit, active_count, total_count = False, 1, 0, len(items)
    return {
        "branches": items,
        "default_branch_id": default_id,
        "active_branch_id": active,
        "is_full_school_admin": is_full,
        # Quota numbers are school-wide. `branches` stays limited to this user's ACL.
        "total_branches": total_count,
        "active_branches": active_count,
        "max_branches": limit,
        "remaining_capacity": max(0, limit - active_count),
        "branch_creation_enabled": enabled,
        "can_create_branch": bool(is_full and enabled and active_count < limit),
    }
