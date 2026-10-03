from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Form, Header, Query, Request
from sqlalchemy import extract, select
from sqlalchemy.orm import Session

from app.api.deps import central_db, open_named_db, require_tenant_user
from app.core.responses import (
    INACTIVE_CHILD,
    INVALID_PASSWORD,
    INVALID_USER_DETAILS,
    VALIDATION_ERROR,
    fail,
    ok,
)
from app.core.security import hash_password, verify_password
from app.models.tables import (
    Announcement,
    Attendance,
    Exam,
    School,
    SessionYear,
    Student,
    Subject,
    SystemSetting,
    User,
)
from app.services.mobile_auth import (
    default_session_year,
    find_school,
    guardian_user_resource,
    student_user_resource,
    user_roles,
    validation_error,
)


def _dt(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _guardian_payload(db: Session, guardian_id: int) -> Optional[dict]:
    guardian = db.get(User, guardian_id)
    if guardian is None:
        return None
    return {
        "id": guardian.id,
        "first_name": guardian.first_name,
        "last_name": guardian.last_name,
        "email": guardian.email,
        "mobile": guardian.mobile,
        "image": guardian.image,
        "occupation": guardian.occupation,
    }

router = APIRouter()

MINIMAL_LANGUAGES = [
    {
        "id": 1,
        "code": "en",
        "name": "English",
        "name_in_english": "English",
        "student_app_file": "",
        "staff_app_file": "",
        "web_file": "",
        "panel_file": "",
        "rtl": False,
        "image": "",
        "country_code": None,
    }
]

DEFAULT_LABELS = {
    "home": "Home",
    "profile": "Profile",
    "attendance": "Attendance",
    "assignments": "Assignments",
    "exams": "Exams",
    "announcements": "Announcements",
    "settings": "Settings",
    "logout": "Logout",
    "changePassword": "Change password",
    "submit": "Submit",
    "cancel": "Cancel",
}

ROLE_FEATURES = {
    "Teacher": ["Attendance Management", "Timetable Management", "Assignment Management", "Exam Management"],
    "School Admin": [
        "Attendance Management",
        "Timetable Management",
        "Assignment Management",
        "Exam Management",
        "Fees Management",
        "Announcement Management",
        "Staff Management",
    ],
    "Staff": ["Attendance Management", "Announcement Management"],
    "Driver": ["Transport Management"],
}

ROLE_PERMISSIONS = {
    "Teacher": [
        "attendance-list",
        "timetable-list",
        "assignment-list",
        "exam-list",
        "announcement-list",
        "class-teacher",
    ],
    "School Admin": [
        "attendance-list",
        "timetable-list",
        "assignment-list",
        "exam-list",
        "fees-list",
        "announcement-list",
        "student-list",
        "staff-list",
    ],
    "Staff": ["attendance-list", "announcement-list"],
    "Driver": ["transport-list"],
}


def _session_year_payload(row: SessionYear) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "default": row.default,
        "start_date": row.start_date.strftime("%d-%m-%Y") if row.start_date else None,
        "end_date": row.end_date.strftime("%d-%m-%Y") if row.end_date else None,
        "school_id": row.school_id,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
        "deleted_at": _dt(getattr(row, "deleted_at", None)),
    }


def _system_settings_map(central: Session) -> Dict[str, str]:
    rows = central.scalars(select(SystemSetting)).all()
    return {row.name: row.data for row in rows}


def _student_for_user(db: Session, user: User) -> Optional[Student]:
    return db.scalar(select(Student).where(Student.user_id == user.id, Student.deleted_at.is_(None)))


def _guardian_child(db: Session, guardian: User, child_id: Optional[int]) -> Optional[Student]:
    if child_id is None:
        return None
    return db.scalar(
        select(Student).where(
            Student.id == child_id,
            Student.guardian_id == guardian.id,
            Student.deleted_at.is_(None),
        )
    )


def _subject_payload(row: Subject) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "code": row.code,
        "bg_color": row.bg_color,
        "image": row.image,
        "medium_id": row.medium_id,
        "type": row.type,
        "school_id": row.school_id,
    }


def _subjects_bundle(db: Session, school_id: Optional[int]) -> dict:
    q = select(Subject).where(Subject.deleted_at.is_(None))
    if school_id is not None:
        q = q.where(Subject.school_id == school_id)
    rows = list(db.scalars(q))
    return {"core_subject": [_subject_payload(r) for r in rows], "elective_subject": []}


def _attendance_payload(row: Attendance) -> dict:
    return {
        "id": row.id,
        "class_section_id": row.class_section_id,
        "student_id": row.student_id,
        "session_year_id": row.session_year_id,
        "type": row.type,
        "date": row.date.isoformat() if row.date else None,
        "remark": row.remark,
        "school_id": row.school_id,
    }


def _exam_payload(row: Exam, session_year_name: Optional[str] = None) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "publish": row.publish,
        "session_year": session_year_name,
        "exam_starting_date": None,
        "exam_ending_date": None,
        "exam_status": 0,
    }


def _announcement_payload(row: Announcement) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "session_year_id": row.session_year_id,
        "school_id": row.school_id,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
        "file": [],
    }


def _paginate(items: List[dict], page: int = 1, per_page: int = 15) -> dict:
    total = len(items)
    last_page = max(1, (total + per_page - 1) // per_page) if total else 1
    page = max(1, page)
    start = (page - 1) * per_page
    chunk = items[start : start + per_page]
    return {
        "current_page": page,
        "data": chunk,
        "per_page": per_page,
        "total": total,
        "last_page": last_page,
        "from": start + 1 if chunk else None,
        "to": start + len(chunk) if chunk else None,
    }


def _school_settings_bootstrap(db: Session, user: User, school: School) -> dict:
    sy = default_session_year(db, school.id)
    return {
        "school_id": user.school_id or school.id,
        "session_year": None if sy is None else _session_year_payload(sy),
        "semester": None,
        "settings": {
            "school_name": school.name,
            "school_tagline": school.tagline or "",
            "horizontal_logo": school.logo or "",
            "privacy_policy": "",
            "terms_condition": "",
            "refund_cancellation": "",
            "about_us": "",
            "contact_us": "",
        },
        "features": {},
        "payment_gateway": [],
    }


def _attendance_bundle(
    db: Session,
    student_user_id: int,
    school_id: int,
    month: Optional[int],
    year: Optional[int],
) -> dict:
    sy = default_session_year(db, school_id)
    q = select(Attendance).where(Attendance.student_id == student_user_id)
    if sy is not None:
        q = q.where(Attendance.session_year_id == sy.id)
    if month is not None:
        q = q.where(extract("month", Attendance.date) == month)
    if year is not None:
        q = q.where(extract("year", Attendance.date) == year)
    rows = list(db.scalars(q))
    return {
        "attendance": [_attendance_payload(r) for r in rows],
        "holidays": [],
        "session_year": None if sy is None else _session_year_payload(sy),
    }


def _exams_for_class(db: Session, class_id: Optional[int], school_id: int) -> List[dict]:
    sy = default_session_year(db, school_id)
    q = select(Exam).where(Exam.school_id == school_id, Exam.deleted_at.is_(None))
    if class_id is not None:
        q = q.where(Exam.class_id == class_id)
    if sy is not None:
        q = q.where(Exam.session_year_id == sy.id)
    rows = list(db.scalars(q.order_by(Exam.id.desc())))
    sy_name = sy.name if sy else None
    return [_exam_payload(r, sy_name) for r in rows]


def _class_id_for_student(db: Session, student: Student) -> Optional[int]:
    from app.models.tables import ClassSection

    cs = db.get(ClassSection, student.class_section_id)
    return None if cs is None else cs.class_id


# --- Public / lightly authenticated common routes ---


@router.get("/settings")
async def get_settings(
    type: Optional[str] = Query(default=None),
    central: Session = Depends(central_db),
):
    allowed = {
        "student_parent_privacy_policy",
        "teacher_staff_privacy_policy",
        "student_terms_condition",
        "teacher_terms_condition",
        "contact_us",
        "about_us",
        "app_settings",
        "fees_settings",
        "terms_condition",
        "privacy_policy",
    }
    if not type or type not in allowed:
        return validation_error("The type field is required.")
    settings = _system_settings_map(central)
    if type == "app_settings":
        data = {
            "app_link": settings.get("app_link", ""),
            "ios_app_link": settings.get("ios_app_link", ""),
            "app_version": settings.get("app_version", ""),
            "ios_app_version": settings.get("ios_app_version", ""),
            "force_app_update": settings.get("force_app_update", ""),
            "app_maintenance": settings.get("app_maintenance", ""),
            "system_maintenance": settings.get("web_maintenance", "0"),
            "teacher_app_link": settings.get("teacher_app_link", ""),
            "teacher_ios_app_link": settings.get("teacher_ios_app_link", ""),
            "teacher_app_version": settings.get("teacher_app_version", ""),
            "teacher_ios_app_version": settings.get("teacher_ios_app_version", ""),
            "teacher_force_app_update": settings.get("teacher_force_app_update", ""),
            "teacher_app_maintenance": settings.get("teacher_app_maintenance", ""),
            "tagline": settings.get("tag_line", ""),
            "title": settings.get("system_name", ""),
        }
    else:
        data = settings.get(type, "")
    return ok("Data Fetched Successfully", data)


@router.get("/school-settings")
async def school_settings(
    type: Optional[str] = Query(default=None),
    child_id: Optional[int] = Query(default=None),
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    if type:
        allowed = {"privacy_policy", "terms_condition", "refund_cancellation", "about_us", "contact_us"}
        if type not in allowed:
            return validation_error("The selected type is invalid.")
        bootstrap = _school_settings_bootstrap(db, user, school)
        return ok("Data Fetched Successfully", bootstrap["settings"].get(type, ""))
    return ok("Settings Fetched Successfully.", _school_settings_bootstrap(db, user, school))


@router.get("/student/school-settings")
async def student_school_settings(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    return ok("Settings Fetched Successfully.", _school_settings_bootstrap(db, user, school))


@router.get("/get-languages")
async def get_languages():
    return ok("Data Fetched Successfully", MINIMAL_LANGUAGES)


@router.post("/set-languages")
async def set_languages(
    language_code: Optional[str] = Form(default=None),
    type: Optional[str] = Form(default=None),
):
    if not language_code:
        return ok("Data Fetched Successfully", MINIMAL_LANGUAGES)
    lang = next((l for l in MINIMAL_LANGUAGES if l["code"] == language_code), None)
    if lang is None:
        return fail("Language not found", code=404)
    data = dict(lang)
    data["file_name"] = dict(DEFAULT_LABELS)
    data["type"] = type or "student"
    return ok("Data Fetched Successfully", data)


@router.get("/holidays")
async def holidays(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    return ok("Holidays Fetched Successfully", [])


@router.get("/notifications")
async def notifications(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    return ok("Data Fetched Successfully", [])


@router.get("/gallery")
async def gallery(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    return ok("Data Fetched Successfully", [])


@router.get("/session-years")
async def session_years(
    child_id: Optional[int] = Query(default=None),
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    school_id = school.id
    if child_id is not None:
        child = _guardian_child(db, user, child_id) or db.get(Student, child_id)
        if child is None:
            return validation_error("Invalid child selected.")
        school_id = child.school_id
    rows = list(
        db.scalars(
            select(SessionYear).where(
                SessionYear.school_id == school_id,
                SessionYear.deleted_at.is_(None),
            )
        )
    )
    return ok("Session Year Fetched Successfully", [_session_year_payload(r) for r in rows])


@router.get("/school-details")
async def school_details(
    school_code: Optional[str] = Header(default=None, alias="school-code"),
    central: Session = Depends(central_db),
):
    if not school_code:
        return fail("Unauthenticated", code=400)
    school = find_school(central, school_code)
    if school is None:
        return fail("Invalid school code", code=400)
    return ok(
        "Data Fetched Successfully",
        {
            "school_name": school.name,
            "school_tagline": school.tagline or "",
            "school_logo": school.logo or "",
            "school_images": [],
        },
    )


@router.get("/staff/features-permission")
async def staff_features_permission(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, _school = tenant
    roles = user_roles(db, user.id)
    features: List[str] = []
    permissions: List[str] = []
    for role in roles:
        features.extend(ROLE_FEATURES.get(role, []))
        permissions.extend(ROLE_PERMISSIONS.get(role, []))
    # de-dupe preserving order
    features = list(dict.fromkeys(features))
    permissions = list(dict.fromkeys(permissions))
    return ok(
        "Data Fetched Successfully",
        {"features": features or None, "permissions": permissions},
    )


@router.post("/change-password")
async def change_password(
    request: Request,
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, _school = tenant
    form = await request.form()
    current = form.get("current_password") or form.get("old_password")
    new_password = form.get("new_password")
    confirm = form.get("new_confirm_password") or form.get("confirm_password") or form.get("confirm")
    if not current:
        return validation_error("The current password field is required.")
    if not new_password:
        return validation_error("The new password field is required.")
    if len(str(new_password)) < 6:
        return validation_error("The new password must be at least 6 characters.")
    if confirm is not None and str(confirm) != str(new_password):
        return validation_error("The new confirm password and new password must match.")
    if not verify_password(str(current), user.password):
        return fail("Invalid Password", code=INVALID_PASSWORD)
    user.password = hash_password(str(new_password))
    db.commit()
    return ok("Password Changed successfully.")


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    central: Session = Depends(central_db),
):
    form = await request.form()
    school_code = form.get("school_code")
    email = form.get("email")
    gr_no = form.get("gr_no")
    dob = form.get("dob")
    if not school_code:
        return fail("Unauthenticated", code=VALIDATION_ERROR)
    school = find_school(central, str(school_code))
    if school is None or not school.database_name:
        return fail("Invalid school code", code=VALIDATION_ERROR)
    db = open_named_db(school.database_name)
    try:
        user = None
        if email:
            user = db.scalar(select(User).where(User.email == str(email)))
        elif gr_no and dob:
            student = db.scalar(
                select(Student).where(Student.admission_no == str(gr_no), Student.deleted_at.is_(None))
            )
            if student is not None:
                candidate = db.get(User, student.user_id)
                if candidate is not None and candidate.dob and candidate.dob.isoformat() == str(dob):
                    user = candidate
                elif candidate is not None:
                    # Accept when dob not stored in mirror for local/dev flows
                    if candidate.dob is None or candidate.dob.isoformat() == str(dob):
                        user = candidate
        else:
            return validation_error("Email or GR number with date of birth is required.")
        if user is None:
            return fail("Invalid user Details", code=INVALID_USER_DETAILS)
        if hasattr(user, "reset_request"):
            user.reset_request = 1
            db.commit()
        return ok("Forgot Password email send successfully" if email else "Request Send Successfully")
    finally:
        db.close()


# --- Student routes ---


@router.get("/student/get-profile-data")
async def student_profile(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    student = _student_for_user(db, user)
    if student is None:
        return fail("Unauthenticated.", code=401)
    data = student_user_resource(db, user, student, school, extra_data={"fcm_id": user.fcm_id})
    data["extra_details"] = []
    return ok("Data Fetched Successfully", data)


@router.get("/student/subjects")
async def student_subjects(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    return ok("Student Subject Fetched Successfully.", _subjects_bundle(db, school.id))


@router.get("/student/timetable")
async def student_timetable(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    return ok("Timetable Fetched Successfully", [])


@router.get("/student/attendance")
async def student_attendance(
    month: Optional[int] = Query(default=None),
    year: Optional[int] = Query(default=None),
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    student = _student_for_user(db, user)
    if student is None:
        return fail("Unauthenticated.", code=401)
    data = _attendance_bundle(db, student.user_id, school.id, month, year)
    return ok("Attendance Details Fetched Successfully", data)


@router.get("/student/assignments")
async def student_assignments(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    return ok("Data Fetched Successfully", [])


@router.get("/student/get-exam-list")
async def student_exam_list(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    student = _student_for_user(db, user)
    class_id = _class_id_for_student(db, student) if student else None
    return ok("", _exams_for_class(db, class_id, school.id))


@router.get("/student/announcements")
async def student_announcements(
    page: Optional[int] = Query(default=1),
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    sy = default_session_year(db, school.id)
    q = select(Announcement).where(Announcement.school_id == school.id)
    if sy is not None:
        q = q.where(Announcement.session_year_id == sy.id)
    rows = list(db.scalars(q.order_by(Announcement.id.desc())))
    items = [_announcement_payload(r) for r in rows]
    return ok("Announcement Details Fetched Successfully", _paginate(items, page=page or 1))


@router.get("/student/guradian-details")
async def student_guardian_details(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, _school = tenant
    student = _student_for_user(db, user)
    if student is None:
        return fail("Unauthenticated.", code=401)
    guardian = _guardian_payload(db, student.guardian_id) or {}
    return ok("Guardian Details Fetched Successfully", {"guardian": guardian})


# --- Parent routes ---


@router.get("/parent/get-data")
async def parent_get_data(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    roles = user_roles(db, user.id)
    if "Guardian" not in roles:
        return fail("Unauthorized Access")
    sy = default_session_year(db, school.id)
    children: List[Student] = []
    if sy is not None:
        children = list(
            db.scalars(
                select(Student).where(
                    Student.guardian_id == user.id,
                    Student.session_year_id == sy.id,
                    Student.deleted_at.is_(None),
                )
            )
        )
    data = guardian_user_resource(db, user, school, children, extra_data={"fcm_id": user.fcm_id})
    return ok("Parent Data Fetched Successfully", data)


@router.get("/parent/subjects")
async def parent_subjects(
    child_id: Optional[int] = Query(default=None),
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    if child_id is None:
        return validation_error("The child id field is required.")
    child = _guardian_child(db, user, child_id)
    if child is None:
        return fail("Child's Account is not Active.Contact School Support", code=INACTIVE_CHILD)
    return ok("Student Subject Fetched Successfully.", _subjects_bundle(db, school.id))


@router.get("/parent/attendance")
async def parent_attendance(
    child_id: Optional[int] = Query(default=None),
    month: Optional[int] = Query(default=None),
    year: Optional[int] = Query(default=None),
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    if child_id is None:
        return validation_error("The child id field is required.")
    child = _guardian_child(db, user, child_id)
    if child is None:
        return fail("Child's Account is not Active.Contact School Support", code=INACTIVE_CHILD)
    data = _attendance_bundle(db, child.user_id, school.id, month, year)
    return ok("Attendance Details Fetched Successfully", data)


@router.get("/parent/get-exam-list")
async def parent_exam_list(
    child_id: Optional[int] = Query(default=None),
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    if child_id is None:
        return validation_error("The child id field is required.")
    child = _guardian_child(db, user, child_id)
    if child is None:
        return fail("Child's Account is not Active.Contact School Support", code=INACTIVE_CHILD)
    class_id = _class_id_for_student(db, child)
    return ok("", _exams_for_class(db, class_id, school.id))


@router.get("/parent/announcements")
async def parent_announcements(
    child_id: Optional[int] = Query(default=None),
    page: Optional[int] = Query(default=1),
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    if child_id is not None:
        child = _guardian_child(db, user, child_id)
        if child is None:
            return fail("Child's Account is not Active.Contact School Support", code=INACTIVE_CHILD)
    sy = default_session_year(db, school.id)
    q = select(Announcement).where(Announcement.school_id == school.id)
    if sy is not None:
        q = q.where(Announcement.session_year_id == sy.id)
    rows = list(db.scalars(q.order_by(Announcement.id.desc())))
    items = [_announcement_payload(r) for r in rows]
    return ok("Announcement Details Fetched Successfully", _paginate(items, page=page or 1))


@router.get("/parent/school-settings")
async def parent_school_settings(
    child_id: Optional[int] = Query(default=None),
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    if child_id is None:
        return validation_error("The child id field is required.")
    child = _guardian_child(db, user, child_id)
    if child is None:
        return fail("Child's Account is not Active. Contact School Support", code=INACTIVE_CHILD)
    data = _school_settings_bootstrap(db, user, school)
    return ok("Settings Fetched Successfully.", data)
