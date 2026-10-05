from __future__ import annotations


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_schema_catalog_includes_core_tables():
    from app.models.catalog import CENTRAL_AND_SCHOOL_TABLES

    for name in ("users", "schools", "students", "fees", "exams", "attendances", "personal_access_tokens"):
        assert name in CENTRAL_AND_SCHOOL_TABLES


def test_student_login_and_logout(client):
    denied = client.post("/api/student/login", data={"password": "secret", "school_code": "DEMO"})
    assert denied.json()["code"] == 102
    bad_school = client.post(
        "/api/student/login",
        data={"gr_number": "GR001", "password": "secret", "school_code": "NOPE"},
    )
    assert bad_school.json()["error"] is True
    assert bad_school.json()["code"] == 101
    ok = client.post(
        "/api/student/login",
        data={"gr_number": "GR001", "password": "secret", "school_code": "DEMO", "fcm_id": "token"},
    )
    body = ok.json()
    assert body["error"] is False
    assert body["token"]
    assert body["data"]["admission_no"] == "GR001"
    assert "class_section" in body["data"]
    assert "school" in body["data"]
    assert "guardian" in body["data"]
    logout = client.post(
        "/api/logout",
        data={"fcm_id": "token"},
        headers={"school-code": "DEMO", "Authorization": f"Bearer {body['token']}"},
    )
    assert logout.json()["error"] is False
    again = client.post("/api/logout", headers={"school-code": "DEMO", "Authorization": f"Bearer {body['token']}"})
    assert again.json()["error"] is True


def test_parent_and_teacher_and_staff_login(client):
    parent = client.post(
        "/api/parent/login",
        data={"email": "guardian@school.test", "password": "secret", "school_code": "DEMO"},
    )
    assert parent.json()["error"] is False
    assert parent.json()["data"]["children"]
    assert parent.json()["data"]["children"][0]["admission_no"] == "GR001"
    assert "school" in parent.json()["data"]["children"][0]
    student_as_teacher = client.post(
        "/api/teacher/login",
        data={"email": "student@school.test", "password": "secret", "school_code": "DEMO"},
    )
    assert student_as_teacher.json()["message"] == "You must have a teacher / Staff role to log in."
    teacher = client.post(
        "/api/staff/login",
        data={"email": "teacher@school.test", "password": "secret", "school_code": "DEMO"},
    )
    assert teacher.json()["error"] is False
    assert teacher.json()["token"]


def test_stub_route_marked_not_ported(client):
    response = client.get("/api/student/lessons", headers={"school-code": "DEMO"})
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is True
    assert body["details"] == "contract-stub"


def test_student_profile_school_settings_session_years(client):
    login = client.post(
        "/api/student/login",
        data={"gr_number": "GR001", "password": "secret", "school_code": "DEMO"},
    )
    token = login.json()["token"]
    headers = {"school-code": "DEMO", "Authorization": f"Bearer {token}"}
    profile = client.get("/api/student/get-profile-data", headers=headers)
    assert profile.json()["error"] is False
    assert profile.json()["data"]["admission_no"] == "GR001"
    assert profile.json()["data"]["guardian"]["email"] == "guardian@school.test"
    settings = client.get("/api/school-settings", headers=headers)
    assert settings.json()["error"] is False
    assert settings.json()["data"]["session_year"]["name"] == "2026"
    years = client.get("/api/session-years", headers=headers)
    assert years.json()["error"] is False
    assert years.json()["data"][0]["name"] == "2026"
    attendance = client.get("/api/student/attendance", headers=headers)
    assert attendance.json()["error"] is False
    assert attendance.json()["data"]["attendance"]


def test_change_password_success(client):
    login = client.post(
        "/api/student/login",
        data={"gr_number": "GR001", "password": "secret", "school_code": "DEMO"},
    )
    token = login.json()["token"]
    headers = {"school-code": "DEMO", "Authorization": f"Bearer {token}"}
    changed = client.post(
        "/api/change-password",
        data={
            "current_password": "secret",
            "new_password": "secret2",
            "new_confirm_password": "secret2",
        },
        headers=headers,
    )
    assert changed.json()["error"] is False
    again = client.post(
        "/api/student/login",
        data={"gr_number": "GR001", "password": "secret2", "school_code": "DEMO"},
    )
    assert again.json()["error"] is False


def test_cross_tenant_denial(client):
    login = client.post(
        "/api/student/login",
        data={"gr_number": "GR001", "password": "secret", "school_code": "DEMO"},
    )
    token = login.json()["token"]
    # Token belongs to DEMO; OTHER school code must not grant access.
    denied = client.get(
        "/api/student/get-profile-data",
        headers={"school-code": "OTHER", "Authorization": f"Bearer {token}"},
    )
    assert denied.json()["error"] is True
    assert denied.json()["code"] == 401
    assert denied.json()["message"] == "Unauthenticated."


def test_same_email_different_schools_isolated(client):
    # OTHER school has GR001 with password other-secret; DEMO uses secret.
    wrong = client.post(
        "/api/student/login",
        data={"gr_number": "GR001", "password": "other-secret", "school_code": "DEMO"},
    )
    assert wrong.json()["error"] is True
    other_ok = client.post(
        "/api/student/login",
        data={"gr_number": "GR001", "password": "other-secret", "school_code": "OTHER"},
    )
    assert other_ok.json()["error"] is False
    demo_ok = client.post(
        "/api/student/login",
        data={"gr_number": "GR001", "password": "secret", "school_code": "DEMO"},
    )
    assert demo_ok.json()["error"] is False


def test_teacher_profile(client):
    login = client.post(
        "/api/teacher/login",
        data={"email": "teacher@school.test", "password": "secret", "school_code": "DEMO"},
    )
    assert login.json()["error"] is False
    token = login.json()["token"]
    profile = client.get(
        "/api/profile",
        headers={"school-code": "DEMO", "Authorization": f"Bearer {token}"},
    )
    body = profile.json()
    assert body["error"] is False
    assert body["data"]["email"] == "teacher@school.test"
    assert any(role["name"] == "Teacher" for role in body["data"]["roles"])


def test_guardian_store_fees(client):
    login = client.post(
        "/api/parent/login",
        data={"email": "guardian@school.test", "password": "secret", "school_code": "DEMO"},
    )
    assert login.json()["error"] is False
    token = login.json()["token"]
    child_id = login.json()["data"]["children"][0]["id"]
    stored = client.post(
        "/api/parent/store-fees",
        data={"transaction_id": "txn_test_1", "child_id": child_id},
        headers={"school-code": "DEMO", "Authorization": f"Bearer {token}"},
    )
    body = stored.json()
    assert body["error"] is False
    assert body["data"]["transaction_id"] == "txn_test_1"


def test_webhook_stripe(client):
    response = client.post("/api/webhook/stripe", json={"type": "payment_intent.succeeded", "id": "evt_1"})
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is False
    assert body["message"] == "Webhook received"
    assert body["code"] == 200
    assert body["data"] is None


def test_admin_login_dashboard_and_domain_lists(client):
    bad = client.post("/api/admin/login", json={"email": "admin@eschool.test", "password": "nope"})
    assert bad.status_code == 401
    missing = client.get("/api/admin/students")
    assert missing.status_code == 401
    login = client.post("/api/admin/login", json={"email": "admin@eschool.test", "password": "secret"})
    assert login.status_code == 200
    assert login.json()["user"]["email"] == "admin@eschool.test"
    assert client.get("/api/admin/me").json()["data"]["email"] == "admin@eschool.test"
    counts = client.get("/api/admin/dashboard").json()["data"]
    assert counts["schools"] == 2  # DEMO + OTHER (cross-school isolation fixtures)
    assert counts["packages"] == 1
    school_login = client.post(
        "/api/admin/login",
        json={"email": "teacher@school.test", "password": "secret", "code": "DEMO"},
    )
    assert school_login.status_code == 200
    students = client.get("/api/admin/students").json()["data"]
    assert students[0]["admission_no"] == "GR001"
    assert client.get("/api/admin/classes").json()["data"][0]["name"] == "Grade 1"
    assert client.get("/api/admin/subjects").json()["data"][0]["name"] == "Math"
    assert client.get("/api/admin/attendances").json()["data"][0]["type"] == 1
    assert client.get("/api/admin/exams").json()["data"][0]["name"] == "Midterm"
    assert client.get("/api/admin/fees").json()["data"][0]["name"] == "Tuition"
    assert client.get("/api/admin/announcements").json()["data"][0]["title"] == "Welcome"
    assert client.get("/api/admin/leaves").json()["data"][0]["reason"] == "Trip"
    assert client.get("/api/admin/expenses").json()["data"][0]["title"] == "Books"
    assert client.get("/api/admin/schools").json()["data"][0]["code"] == "DEMO"
    assert client.get("/api/admin/packages").json()["data"][0]["name"] == "Basic"
    client.post("/api/admin/logout")
    assert client.get("/api/admin/me").status_code == 401
