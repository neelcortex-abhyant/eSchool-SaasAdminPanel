"""Teacher-facing operations (Modules 1–6) using legacy teacher PAT identity.

Authenticated principal is a Spatie ``Teacher`` + ``Staff`` row. Client-supplied
``teacher_user_id`` / evaluator ids are ignored; identity is always forced from
the token. School-admin JWT routes remain unchanged.

Offline exam marks (teacher portal): the schedule must have
``teacher_user_id`` equal to the authenticated teacher. Schedules with
``teacher_user_id IS NULL`` are admin-owned until a teacher is assigned; matching
``TeacherAssignment`` alone is not sufficient for teacher writes (avoids
multi-teacher shared edits). School-admin mark APIs are unaffected.

Employment: ``on_leave`` remains allowed here. Product convention in
``school_teachers`` is that employment_status does not by itself block access;
only ``resigned`` / ``terminated`` are rejected on the teacher portal.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.tables import (
    Homework,
    HomeworkSubmission,
    OfflineExamMark,
    OfflineExamSchedule,
    OnlineAssessment,
    Staff,
    StudyMaterial,
    User,
)
from app.services.v1 import school_homework as homework_svc
from app.services.v1 import school_offline_exams as offline_svc
from app.services.v1 import school_online_assessments as oa_svc
from app.services.v1 import school_study_materials as materials_svc
from app.services.v1 import school_timetable as timetable_svc
from app.services.v1.school_academics import (
    AcademicError,
    _envelope,
    _owned,
    _page,
    _staff_for_teacher_user,
    _user_name,
    list_teacher_assignments,
)
from app.services.v1.school_teachers import _user_has_teacher_role

_INACTIVE_EMPLOYMENT = frozenset({"resigned", "terminated"})


def resolve_active_teacher(db: Session, school_id: int, user: User) -> tuple[User, Staff]:
    if user.school_id != school_id or user.deleted_at is not None:
        raise AcademicError(404, "Record not found")
    if getattr(user, "status", 1) != 1:
        raise AcademicError(403, "Teacher account is not active")
    if not _user_has_teacher_role(db, user.id, school_id):
        raise AcademicError(403, "Teacher role required")
    staff = _staff_for_teacher_user(db, school_id, user.id)
    status = (staff.employment_status or "active").strip().lower()
    if status in _INACTIVE_EMPLOYMENT:
        raise AcademicError(403, "Teacher employment is not active")
    return user, staff


def actor_id(user: User) -> str:
    """Audit/evaluator id for legacy teacher principals (distinct from v1 UUIDs)."""
    return f"teacher:{user.id}"[:36]


def _force_self(body: dict, teacher_user_id: int) -> dict:
    data = dict(body or {})
    data.pop("teacher_user_id", None)
    data.pop("staff_id", None)
    data.pop("school_id", None)
    data.pop("evaluated_by_user_id", None)
    data.pop("evaluated_by_v1_user_id", None)
    data.pop("actor_v1_user_id", None)
    data["teacher_user_id"] = teacher_user_id
    return data


def _assert_owns_homework(db: Session, school_id: int, homework_id: int, teacher_user_id: int) -> Homework:
    hw = _owned(db, Homework, homework_id, school_id)
    if hw.teacher_user_id != teacher_user_id:
        raise AcademicError(404, "Record not found")
    return hw


def _assert_owns_material(db: Session, school_id: int, material_id: int, teacher_user_id: int) -> StudyMaterial:
    row = _owned(db, StudyMaterial, material_id, school_id)
    if row.teacher_user_id != teacher_user_id:
        raise AcademicError(404, "Record not found")
    return row


def _assert_owns_assessment(
    db: Session, school_id: int, assessment_id: int, teacher_user_id: int
) -> OnlineAssessment:
    row = _owned(db, OnlineAssessment, assessment_id, school_id)
    if row.teacher_user_id != teacher_user_id:
        raise AcademicError(404, "Record not found")
    return row


def _assert_schedule_for_teacher(
    db: Session, school_id: int, schedule_id: int, teacher_user_id: int, staff_id: int
) -> OfflineExamSchedule:
    """Teacher writes require an explicitly assigned schedule teacher.

    Unassigned schedules (``teacher_user_id IS NULL``) are not writable via the
    teacher portal — school-admin must set ``teacher_user_id`` or enter marks
    on school-admin routes.
    """
    schedule = _owned(db, OfflineExamSchedule, schedule_id, school_id)
    if schedule.teacher_user_id is None or schedule.teacher_user_id != teacher_user_id:
        raise AcademicError(404, "Record not found")
    try:
        homework_svc._assert_teacher_assignment(
            db,
            school_id,
            staff_id=staff_id,
            subject_id=schedule.subject_id,
            class_section_id=schedule.class_section_id,
            session_year_id=schedule.session_year_id,
        )
    except AcademicError as exc:
        if exc.status_code == 422:
            raise AcademicError(404, "Record not found") from None
        raise
    return schedule


# --- Profile / assignments / timetable ---


def me(db: Session, school_id: int, user: User) -> dict:
    teacher, staff = resolve_active_teacher(db, school_id, user)
    return {
        "teacher_user_id": teacher.id,
        "staff_id": staff.id,
        "name": _user_name(teacher),
        "email": teacher.email,
        "employee_id": staff.employee_id,
        "employment_status": staff.employment_status,
        "department": staff.department,
        "designation": staff.designation,
    }


def my_assignments(
    db: Session,
    school_id: int,
    user: User,
    *,
    page: int,
    page_size: int,
    subject_id: int | None = None,
    class_section_id: int | None = None,
    session_year_id: int | None = None,
) -> dict:
    resolve_active_teacher(db, school_id, user)
    return list_teacher_assignments(
        db,
        school_id,
        page,
        page_size,
        teacher_id=user.id,
        subject_id=subject_id,
        class_section_id=class_section_id,
        session_year_id=session_year_id,
    )


def my_timetable_daily(
    db: Session, school_id: int, user: User, *, day: str, session_year_id: int
) -> dict:
    resolve_active_teacher(db, school_id, user)
    return timetable_svc.teacher_daily_timetable(
        db, school_id, user.id, day=day, session_year_id=session_year_id
    )


def my_timetable_weekly(db: Session, school_id: int, user: User, *, session_year_id: int) -> dict:
    resolve_active_teacher(db, school_id, user)
    return timetable_svc.teacher_weekly_timetable(
        db, school_id, user.id, session_year_id=session_year_id
    )


def my_timetable_entries(
    db: Session,
    school_id: int,
    user: User,
    *,
    page: int,
    page_size: int,
    session_year_id: int,
    day: str | None = None,
) -> dict:
    resolve_active_teacher(db, school_id, user)
    return timetable_svc.list_teacher_timetable(
        db,
        school_id,
        user.id,
        page=page,
        page_size=page_size,
        session_year_id=session_year_id,
        day=day,
    )


# --- Homework ---


def create_homework(db: Session, school_id: int, user: User, body: dict) -> dict:
    resolve_active_teacher(db, school_id, user)
    return homework_svc.create_homework(db, school_id, _force_self(body, user.id))


def list_homework(
    db: Session,
    school_id: int,
    user: User,
    *,
    page: int,
    page_size: int,
    session_year_id: int | None = None,
    class_section_id: int | None = None,
    subject_id: int | None = None,
    q: str = "",
) -> dict:
    resolve_active_teacher(db, school_id, user)
    return homework_svc.list_homework(
        db,
        school_id,
        page=page,
        page_size=page_size,
        session_year_id=session_year_id,
        class_section_id=class_section_id,
        subject_id=subject_id,
        teacher_user_id=user.id,
        q=q,
    )


def get_homework(db: Session, school_id: int, user: User, homework_id: int) -> dict:
    resolve_active_teacher(db, school_id, user)
    _assert_owns_homework(db, school_id, homework_id, user.id)
    return homework_svc.get_homework(db, school_id, homework_id)


def update_homework(db: Session, school_id: int, user: User, homework_id: int, body: dict) -> dict:
    resolve_active_teacher(db, school_id, user)
    _assert_owns_homework(db, school_id, homework_id, user.id)
    data = _force_self(body, user.id)
    return homework_svc.update_homework(db, school_id, homework_id, data)


def delete_homework(db: Session, school_id: int, user: User, homework_id: int) -> dict:
    resolve_active_teacher(db, school_id, user)
    _assert_owns_homework(db, school_id, homework_id, user.id)
    return homework_svc.soft_delete_homework(db, school_id, homework_id)


def list_submissions(
    db: Session,
    school_id: int,
    user: User,
    homework_id: int,
    *,
    page: int,
    page_size: int,
    status_filter: str | None = None,
    is_late: bool | None = None,
) -> dict:
    resolve_active_teacher(db, school_id, user)
    _assert_owns_homework(db, school_id, homework_id, user.id)
    return homework_svc.list_submissions(
        db,
        school_id,
        homework_id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        is_late=is_late,
    )


def homework_summary(db: Session, school_id: int, user: User, homework_id: int) -> dict:
    resolve_active_teacher(db, school_id, user)
    _assert_owns_homework(db, school_id, homework_id, user.id)
    return homework_svc.homework_summary(db, school_id, homework_id)


def evaluate_submission(
    db: Session, school_id: int, user: User, submission_id: int, body: dict
) -> dict:
    resolve_active_teacher(db, school_id, user)
    row = _owned(db, HomeworkSubmission, submission_id, school_id)
    _assert_owns_homework(db, school_id, row.homework_id, user.id)
    result = homework_svc.evaluate_submission(
        db,
        school_id,
        submission_id,
        body,
        evaluator_user_id=actor_id(user),
    )
    result["evaluated_by_actor"] = "teacher"
    return result


def append_homework_attachment(
    db: Session,
    school_id: int,
    user: User,
    homework_id: int,
    *,
    file_bytes: bytes,
    claimed_filename: str | None,
) -> dict:
    resolve_active_teacher(db, school_id, user)
    _assert_owns_homework(db, school_id, homework_id, user.id)
    return homework_svc.append_stored_attachment_to_homework(
        db,
        school_id,
        homework_id,
        file_bytes=file_bytes,
        claimed_filename=claimed_filename,
    )


# --- Study materials ---


def create_material(
    db: Session,
    school_id: int,
    user: User,
    body: dict,
    *,
    file_bytes: bytes | None = None,
    claimed_filename: str | None = None,
) -> dict:
    resolve_active_teacher(db, school_id, user)
    return materials_svc.create_material(
        db,
        school_id,
        _force_self(body, user.id),
        actor_v1_user_id=actor_id(user),
        file_bytes=file_bytes,
        claimed_filename=claimed_filename,
    )


def list_materials(
    db: Session,
    school_id: int,
    user: User,
    *,
    page: int,
    page_size: int,
    session_year_id: int | None = None,
    class_section_id: int | None = None,
    subject_id: int | None = None,
    resource_type: str | None = None,
    q: str = "",
) -> dict:
    resolve_active_teacher(db, school_id, user)
    return materials_svc.list_materials(
        db,
        school_id,
        page=page,
        page_size=page_size,
        session_year_id=session_year_id,
        class_section_id=class_section_id,
        subject_id=subject_id,
        teacher_user_id=user.id,
        resource_type=resource_type,
        q=q,
    )


def get_material(db: Session, school_id: int, user: User, material_id: int) -> dict:
    resolve_active_teacher(db, school_id, user)
    _assert_owns_material(db, school_id, material_id, user.id)
    return materials_svc.get_material(db, school_id, material_id)


def update_material(db: Session, school_id: int, user: User, material_id: int, body: dict) -> dict:
    resolve_active_teacher(db, school_id, user)
    _assert_owns_material(db, school_id, material_id, user.id)
    return materials_svc.update_material(
        db, school_id, material_id, _force_self(body, user.id), actor_v1_user_id=actor_id(user)
    )


def delete_material(db: Session, school_id: int, user: User, material_id: int) -> dict:
    resolve_active_teacher(db, school_id, user)
    _assert_owns_material(db, school_id, material_id, user.id)
    return materials_svc.soft_delete_material(db, school_id, material_id)


def download_material(db: Session, school_id: int, user: User, material_id: int):
    resolve_active_teacher(db, school_id, user)
    _assert_owns_material(db, school_id, material_id, user.id)
    return materials_svc.get_file_bytes(db, school_id, material_id)


# --- Offline exam marks ---


def list_my_schedules(
    db: Session,
    school_id: int,
    user: User,
    *,
    page: int,
    page_size: int,
    exam_id: int | None = None,
    session_year_id: int | None = None,
    class_section_id: int | None = None,
    subject_id: int | None = None,
    exam_date: date | None = None,
) -> dict:
    teacher, _staff = resolve_active_teacher(db, school_id, user)
    page, page_size = _page(page, page_size)
    # Only schedules explicitly assigned to this teacher (not NULL / not others).
    query = db.query(OfflineExamSchedule).filter(
        OfflineExamSchedule.school_id == school_id,
        OfflineExamSchedule.deleted_at.is_(None),
        OfflineExamSchedule.teacher_user_id == teacher.id,
    )
    if exam_id is not None:
        query = query.filter(OfflineExamSchedule.exam_id == exam_id)
    if session_year_id is not None:
        query = query.filter(OfflineExamSchedule.session_year_id == session_year_id)
    if class_section_id is not None:
        query = query.filter(OfflineExamSchedule.class_section_id == class_section_id)
    if subject_id is not None:
        query = query.filter(OfflineExamSchedule.subject_id == subject_id)
    if exam_date is not None:
        query = query.filter(OfflineExamSchedule.exam_date == exam_date)

    total = query.count()
    rows = (
        query.order_by(OfflineExamSchedule.exam_date.asc(), OfflineExamSchedule.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _envelope([offline_svc._schedule_item(db, r) for r in rows], total, page, page_size)


def upsert_mark(
    db: Session,
    school_id: int,
    user: User,
    schedule_id: int,
    body: dict,
    *,
    reason: str | None = None,
) -> dict:
    _teacher, staff = resolve_active_teacher(db, school_id, user)
    _assert_schedule_for_teacher(db, school_id, schedule_id, user.id, staff.id)
    return offline_svc.upsert_mark(
        db,
        school_id,
        schedule_id,
        body,
        actor_v1_user_id=actor_id(user),
        reason=reason,
    )


def bulk_upsert_marks(
    db: Session, school_id: int, user: User, schedule_id: int, items: list
) -> dict:
    _teacher, staff = resolve_active_teacher(db, school_id, user)
    _assert_schedule_for_teacher(db, school_id, schedule_id, user.id, staff.id)
    return offline_svc.bulk_upsert_marks(
        db,
        school_id,
        schedule_id,
        items,
        actor_v1_user_id=actor_id(user),
    )


def list_marks(
    db: Session,
    school_id: int,
    user: User,
    *,
    page: int,
    page_size: int,
    schedule_id: int,
    student_id: int | None = None,
) -> dict:
    _teacher, staff = resolve_active_teacher(db, school_id, user)
    _assert_schedule_for_teacher(db, school_id, schedule_id, user.id, staff.id)
    return offline_svc.list_marks(
        db,
        school_id,
        page=page,
        page_size=page_size,
        schedule_id=schedule_id,
        student_id=student_id,
    )


def list_mark_audits(db: Session, school_id: int, user: User, mark_id: int) -> list:
    _teacher, staff = resolve_active_teacher(db, school_id, user)
    mark = _owned(db, OfflineExamMark, mark_id, school_id)
    _assert_schedule_for_teacher(db, school_id, mark.schedule_id, user.id, staff.id)
    return offline_svc.list_mark_audits(db, school_id, mark_id)


# --- Online assessments (owned by teacher) ---


def create_assessment(db: Session, school_id: int, user: User, body: dict) -> dict:
    resolve_active_teacher(db, school_id, user)
    return oa_svc.create_assessment(db, school_id, _force_self(body, user.id))


def list_assessments(
    db: Session,
    school_id: int,
    user: User,
    *,
    page: int,
    page_size: int,
    session_year_id: int | None = None,
    class_section_id: int | None = None,
    subject_id: int | None = None,
    status: str | None = None,
    q: str = "",
) -> dict:
    resolve_active_teacher(db, school_id, user)
    return oa_svc.list_assessments(
        db,
        school_id,
        page=page,
        page_size=page_size,
        session_year_id=session_year_id,
        class_section_id=class_section_id,
        subject_id=subject_id,
        teacher_user_id=user.id,
        status=status,
        q=q,
    )


def get_assessment(db: Session, school_id: int, user: User, assessment_id: int) -> dict:
    resolve_active_teacher(db, school_id, user)
    _assert_owns_assessment(db, school_id, assessment_id, user.id)
    return oa_svc.get_assessment(db, school_id, assessment_id)


def list_attempts(
    db: Session,
    school_id: int,
    user: User,
    assessment_id: int,
    *,
    page: int,
    page_size: int,
) -> dict:
    resolve_active_teacher(db, school_id, user)
    _assert_owns_assessment(db, school_id, assessment_id, user.id)
    return oa_svc.list_assessment_attempts(
        db, school_id, assessment_id, page=page, page_size=page_size
    )
