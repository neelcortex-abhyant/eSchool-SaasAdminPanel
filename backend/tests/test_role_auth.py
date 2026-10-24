"""Role-specific login and authorization for the mobile API and legacy admin panel.

Uses the isolated fixtures from tests/conftest.py (DEMO + OTHER schools).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.database import session_factory
from app.core.security import hash_password, sign_session, utcnow
from app.models.tables import USER_MODEL, ModelHasRole, PersonalAccessToken, Role, School, Student, User

GENERIC = "Invalid Login Credentials"


def _school(db, code: str) -> School:
    return db.scalar(select(School).where(School.code == code))


def _assign(db, user_id: int, role_name: str, school_id: int) -> None:
    role = db.scalar(select(Role).where(Role.name == role_name, Role.school_id == school_id))
    if role is None:
        role = Role(name=role_name, guard_name="web", school_id=school_id, created_at=utcnow())
        db.add(role)
        db.flush()
    db.add(ModelHasRole(role_id=role.id, model_type=USER_MODEL, model_id=user_id))


def _add_user(email: str, roles: list[str], *, password: str = "secret", status: int = 1) -> int:
    db = session_factory()()
    try:
        school = _school(db, "DEMO")
        user = User(
            first_name="Extra",
            last_name="User",
            email=email,
            password=hash_password(password),
            status=status,
            school_id=school.id,
            created_at=utcnow(),
        )
        db.add(user)
        db.flush()
        for role in roles:
            _assign(db, user.id, role, school.id)
        db.commit()
        return user.id
    finally:
        db.close()


def _set_status(email: str, status: int) -> None:
    db = session_factory()()
    try:
        for user in db.scalars(select(User).where(User.email == email)):
            user.status = status
        db.commit()
    finally:
        db.close()


def _student_id(code: str) -> int:
    db = session_factory()()
    try:
        school = _school(db, code)
        return db.scalar(select(Student.id).where(Student.school_id == school.id))
    finally:
        db.close()


def _unlinked_demo_student() -> int:
    """A DEMO student whose guardian is not guardian@school.test."""
    uid = _add_user("GR777", ["Student"])
    db = session_factory()()
    try:
        school = _school(db, "DEMO")
        template = db.scalar(select(Student).where(Student.school_id == school.id))
        other_parent = _add_user("other-parent@school.test", ["Guardian"])
        row = Student(
            user_id=uid,
            class_section_id=template.class_section_id,
            admission_no="GR777",
            roll_number=2,
            admission_date=date(2026, 4, 1),
            school_id=school.id,
            guardian_id=other_parent,
            session_year_id=template.session_year_id,
            created_at=utcnow(),
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _login(client, login_as: str, **form):
    """POST /api/{login_as}/login. Extra form keys (e.g. role=) are forwarded as-is."""
    data = {"school_code": "DEMO", **form}
    return client.post(f"/api/{login_as}/login", data=data).json()


def _student_token(client) -> str:
    return _login(client, "student", gr_number="GR001", password="secret")["token"]


def _parent_token(client) -> str:
    return _login(client, "parent", email="guardian@school.test", password="secret")["token"]


def _teacher_token(client) -> str:
    return _login(client, "teacher", email="teacher@school.test", password="secret")["token"]


def _h(token: str, code: str = "DEMO") -> dict[str, str]:
    return {"school-code": code, "Authorization": f"Bearer {token}"}


# --- Student login ---


def test_student_login_rejects_other_roles_and_bad_input(client):
    assert _login(client, "student", gr_number="GR001", password="secret")["error"] is False
    for gr in ("teacher@school.test", "guardian@school.test"):
        body = _login(client, "student", gr_number=gr, password="secret")
        assert body["error"] is True and body["code"] == 101 and body["message"] == GENERIC
        assert "token" not in body
    wrong = _login(client, "student", gr_number="GR001", password="nope")
    missing = _login(client, "student", gr_number="NOPE999", password="secret")
    assert wrong["message"] == missing["message"] == GENERIC
    assert _login(client, "student", password="secret")["code"] == 102
    assert _login(client, "student", gr_number="GR001")["code"] == 102


def test_student_login_ignores_role_in_form(client):
    body = _login(client, "student", gr_number="GR001", password="secret", role="Teacher")
    assert body["error"] is False
    denied = client.get("/api/staff/counter", headers=_h(body["token"]))
    assert denied.json()["error"] is True
    assert denied.json()["message"] == "Unauthorized Access"


# --- Parent login ---


def test_parent_login_rejects_other_roles_and_bad_input(client):
    assert _login(client, "parent", email="guardian@school.test", password="secret")["error"] is False
    for email in ("teacher@school.test", "student@school.test"):
        body = _login(client, "parent", email=email, password="secret")
        assert body["error"] is True and body["message"] == GENERIC and "token" not in body
    assert _login(client, "parent", email="guardian@school.test", password="nope")["message"] == GENERIC
    assert _login(client, "parent", email="ghost@school.test", password="secret")["message"] == GENERIC
    assert _login(client, "parent", email="not-an-email", password="secret")["code"] == 102
    assert _login(client, "parent", password="secret")["code"] == 102


def test_parent_login_inactive_account(client):
    _set_status("guardian@school.test", 0)
    body = _login(client, "parent", email="guardian@school.test", password="secret")
    assert body["error"] is True
    assert body["code"] == 116
    assert "token" not in body


# --- Teacher / staff login ---


def test_teacher_login_rejects_other_roles_without_leaking_them(client):
    assert _login(client, "teacher", email="teacher@school.test", password="secret")["error"] is False
    _add_user("norole@school.test", [])
    for email in ("student@school.test", "guardian@school.test", "norole@school.test"):
        body = _login(client, "teacher", email=email, password="secret")
        assert body["error"] is True and body["code"] == 101 and body["message"] == GENERIC
        assert "token" not in body
    # A wrong password for a student looks exactly like a wrong password for a teacher.
    a = _login(client, "teacher", email="student@school.test", password="nope")
    b = _login(client, "teacher", email="teacher@school.test", password="nope")
    c = _login(client, "teacher", email="ghost@school.test", password="nope")
    assert a == b == c
    assert _login(client, "teacher", email="teacher@school.test")["code"] == 102


def test_staff_login_allows_school_admin_and_blocks_inactive_teacher(client):
    _add_user("schooladmin@school.test", ["School Admin"])
    _add_user("admin-parent@school.test", ["School Admin", "Guardian"])
    for email in ("schooladmin@school.test", "admin-parent@school.test"):
        assert _login(client, "staff", email=email, password="secret")["error"] is False
    _set_status("teacher@school.test", 0)
    body = _login(client, "teacher", email="teacher@school.test", password="secret")
    assert body["error"] is True and body["code"] == 116


# --- Mobile tokens ---


@pytest.mark.parametrize(
    "authorization",
    [None, "", "Bearer", "Bearer garbage", "Bearer 1|wrong", "Bearer abc|def", "Basic dXNlcjpwYXNz"],
)
def test_missing_or_malformed_token(client, authorization):
    headers = {"school-code": "DEMO"}
    if authorization is not None:
        headers["Authorization"] = authorization
    body = client.get("/api/student/get-profile-data", headers=headers).json()
    assert body["error"] is True and body["code"] == 401


def test_tampered_expired_and_revoked_tokens(client):
    token = _student_token(client)
    token_id, plain = token.split("|", 1)
    tampered = f"{token_id}|{plain[:-1]}{'A' if plain[-1] != 'A' else 'B'}"
    assert client.get("/api/student/get-profile-data", headers=_h(tampered)).json()["code"] == 401
    # Point the secret at another token row.
    other = _parent_token(client)
    swapped = f"{other.split('|', 1)[0]}|{plain}"
    assert client.get("/api/student/get-profile-data", headers=_h(swapped)).json()["code"] == 401

    db = session_factory()()
    try:
        row = db.get(PersonalAccessToken, int(token_id))
        row.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    assert client.get("/api/student/get-profile-data", headers=_h(token)).json()["code"] == 401

    fresh = _student_token(client)
    assert client.post("/api/logout", headers=_h(fresh)).json()["error"] is False
    assert client.get("/api/student/get-profile-data", headers=_h(fresh)).json()["code"] == 401


def test_token_stops_working_after_deactivation(client):
    token = _teacher_token(client)
    assert client.get("/api/profile", headers=_h(token)).json()["error"] is False
    _set_status("teacher@school.test", 0)
    body = client.get("/api/profile", headers=_h(token)).json()
    assert body["error"] is True and body["code"] == 116


def test_token_rejected_for_other_school_code(client):
    token = _teacher_token(client)
    body = client.get("/api/profile", headers=_h(token, code="OTHER")).json()
    assert body["error"] is True and body["code"] == 401


# --- Cross-role API access ---


@pytest.mark.parametrize(
    ("who", "path"),
    [
        ("student", "/api/parent/get-data"),
        ("student", "/api/staff/counter"),
        ("student", "/api/staff/teachers"),
        ("student", "/api/staff/features-permission"),
        ("parent", "/api/student/get-profile-data"),
        ("parent", "/api/student/subjects"),
        ("parent", "/api/student/announcements"),
        ("parent", "/api/staff/counter"),
        ("teacher", "/api/student/subjects"),
        ("teacher", "/api/student/attendance"),
        ("teacher", "/api/parent/get-data"),
        ("teacher", "/api/parent/subjects?child_id=1"),
    ],
)
def test_role_cannot_use_another_roles_api(client, who, path):
    token = {"student": _student_token, "parent": _parent_token, "teacher": _teacher_token}[who](client)
    body = client.get(path, headers=_h(token)).json()
    assert body["error"] is True
    assert body["message"] == "Unauthorized Access"


def test_role_query_and_header_spoofing_ignored(client):
    token = _student_token(client)
    headers = {**_h(token), "X-Role": "Guardian", "role": "School Admin"}
    body = client.get("/api/parent/get-data?role=Guardian", headers=headers).json()
    assert body["message"] == "Unauthorized Access"


def test_each_role_reaches_its_own_api(client):
    assert client.get("/api/student/get-profile-data", headers=_h(_student_token(client))).json()["error"] is False
    assert client.get("/api/parent/get-data", headers=_h(_parent_token(client))).json()["error"] is False
    assert client.get("/api/staff/counter", headers=_h(_teacher_token(client))).json()["error"] is False


# --- Parent / child links ---


def test_parent_cannot_reach_unlinked_or_other_school_child(client):
    token = _parent_token(client)
    own = _student_id("DEMO")
    # conftest links this guardian to an OTHER-school student as well.
    foreign = _student_id("OTHER")
    unlinked = _unlinked_demo_student()

    ok = client.get(f"/api/parent/subjects?child_id={own}", headers=_h(token)).json()
    assert ok["error"] is False
    for child in (foreign, unlinked):
        for path in ("/api/parent/subjects", "/api/parent/attendance", "/api/parent/get-exam-list"):
            body = client.get(f"{path}?child_id={child}", headers=_h(token)).json()
            assert body["error"] is True and body["code"] == 115, (path, child)
        stored = client.post(
            "/api/parent/store-fees",
            data={"transaction_id": "txn_x", "child_id": child},
            headers=_h(token),
        ).json()
        assert stored["error"] is True


def test_session_years_child_id_idor(client):
    foreign = _student_id("OTHER")
    unlinked = _unlinked_demo_student()
    for token in (_parent_token(client), _student_token(client), _teacher_token(client)):
        for child in (foreign, unlinked):
            body = client.get(f"/api/session-years?child_id={child}", headers=_h(token)).json()
            assert body["error"] is True
            assert body["message"] == "Invalid child selected."
    own = client.get(f"/api/session-years?child_id={_student_id('DEMO')}", headers=_h(_parent_token(client))).json()
    assert own["error"] is False and own["data"][0]["name"] == "2026"


def test_student_details_scoped_to_caller(client):
    own = _student_id("DEMO")
    unlinked = _unlinked_demo_student()

    student = _h(_student_token(client))
    assert client.get(f"/api/student-details?student_id={own}", headers=student).json()["error"] is False
    assert client.get(f"/api/student-details?student_id={unlinked}", headers=student).json()["error"] is True

    parent = _h(_parent_token(client))
    assert client.get(f"/api/student-details?student_id={own}", headers=parent).json()["error"] is False
    assert client.get(f"/api/student-details?student_id={unlinked}", headers=parent).json()["error"] is True

    teacher = _h(_teacher_token(client))
    for sid in (own, unlinked):
        assert client.get(f"/api/student-details?student_id={sid}", headers=teacher).json()["error"] is False
    foreign = _student_id("OTHER")
    assert client.get(f"/api/student-details?student_id={foreign}", headers=teacher).json()["error"] is True


# --- Legacy admin panel (/api/admin) ---


@pytest.mark.parametrize("email", ["GR001", "guardian@school.test", "student@school.test"])
def test_admin_panel_login_rejects_students_and_parents(client, email):
    res = client.post("/api/admin/login", json={"email": email, "password": "secret", "code": "DEMO"})
    assert res.status_code == 401
    assert res.json()["message"] == "The provided credentials do not match our records."
    assert "eschool_session" not in res.cookies
    assert client.get("/api/admin/students").status_code == 401


def test_admin_panel_rechecks_role_on_each_request(client):
    db = session_factory()()
    try:
        guardian = db.scalar(select(User).where(User.email == "guardian@school.test"))
        school = _school(db, "DEMO")
        cookie = sign_session({"uid": guardian.id, "db": None, "code": "DEMO", "school_id": school.id})
    finally:
        db.close()
    client.cookies.set("eschool_session", cookie)
    assert client.get("/api/admin/students").status_code == 403
    client.cookies.set("eschool_session", cookie[:-2] + "xx")
    assert client.get("/api/admin/students").status_code == 401


def test_admin_panel_cookie_rejected_after_deactivation(client):
    assert client.post(
        "/api/admin/login", json={"email": "teacher@school.test", "password": "secret", "code": "DEMO"}
    ).status_code == 200
    assert client.get("/api/admin/me").status_code == 200
    _set_status("teacher@school.test", 0)
    assert client.get("/api/admin/me").status_code == 401
