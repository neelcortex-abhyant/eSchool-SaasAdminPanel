"""Notification enqueue + FCM HTTP v1 delivery via FastAPI BackgroundTasks.

No Celery. If Firebase is not configured, notifications stay ``delivery=queued``
(never fake ``sent``). Delivery uses httpx + signed JWT (cryptography).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.tables import (
    Leave,
    Notification,
    School,
    Staff,
    Student,
    SystemSetting,
    User,
)
from app.services.v1.school_academics import AcademicError, _commit, _now

logger = logging.getLogger(__name__)

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
TOKEN_URI = "https://oauth2.googleapis.com/token"
MAX_RETRIES_DEFAULT = 3

# Injectable for offline tests (returns None → use real httpx).
_fcm_sender: Callable[[str, str, dict], dict] | None = None


def set_fcm_sender_for_tests(fn: Callable[[str, str, dict], dict] | None) -> None:
    global _fcm_sender
    _fcm_sender = fn


def _firebase_creds_from_env() -> dict[str, str] | None:
    settings = get_settings()
    raw = (settings.firebase_service_account_json or "").strip()
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Treat as filesystem path to JSON.
            try:
                with open(raw, encoding="utf-8") as handle:
                    data = json.load(handle)
            except OSError as exc:
                logger.warning("firebase_service_account_json unreadable: %s", exc)
                return None
        if isinstance(data, dict) and data.get("private_key") and data.get("client_email"):
            project = data.get("project_id") or settings.firebase_project_id
            if not project:
                return None
            return {
                "project_id": str(project),
                "client_email": str(data["client_email"]),
                "private_key": str(data["private_key"]).replace("\\n", "\n"),
            }
    project = (settings.firebase_project_id or "").strip()
    email = (settings.firebase_client_email or "").strip()
    key = (settings.firebase_private_key.get_secret_value() or "").strip().replace("\\n", "\n")
    if project and email and key:
        return {"project_id": project, "client_email": email, "private_key": key}
    return None


def _firebase_configured_flag(db: Session | None) -> bool:
    if db is None:
        return False
    row = db.scalar(select(SystemSetting).where(SystemSetting.name == "firebase_private_key"))
    return bool(row and row.data)


def has_firebase_credentials(db: Session | None = None) -> bool:
    """True when env service-account credentials are usable."""
    if _firebase_creds_from_env() is not None:
        return True
    # Legacy short setting alone is insufficient for FCM v1 (key truncated to 255).
    if _firebase_configured_flag(db):
        logger.info(
            "firebase_private_key system setting is present but incomplete for FCM v1; "
            "set FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_PROJECT_ID/"
            "FIREBASE_CLIENT_EMAIL/FIREBASE_PRIVATE_KEY"
        )
    return False


def _google_access_token(creds: dict[str, str]) -> str:
    """Create a short-lived OAuth access token via JWT bearer grant."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claim = {
        "iss": creds["client_email"],
        "scope": FCM_SCOPE,
        "aud": TOKEN_URI,
        "iat": now,
        "exp": now + 3600,
    }

    def _b64(data: bytes) -> str:
        import base64

        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    signing_input = f"{_b64(json.dumps(header, separators=(',', ':')).encode())}.{_b64(json.dumps(claim, separators=(',', ':')).encode())}"
    private_key = serialization.load_pem_private_key(
        creds["private_key"].encode("utf-8"), password=None
    )
    signature = private_key.sign(  # type: ignore[union-attr]
        signing_input.encode("ascii"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    assertion = f"{signing_input}.{_b64(signature)}"
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            TOKEN_URI,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise RuntimeError("OAuth token response missing access_token")
        return str(token)


def _send_fcm_message(access_token: str, project_id: str, message: dict) -> dict:
    if _fcm_sender is not None:
        return _fcm_sender(access_token, project_id, message)
    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            url,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"message": message},
        )
        body: dict[str, Any]
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:500]}
        return {"status_code": resp.status_code, "body": body, "ok": 200 <= resp.status_code < 300}


def _audience_users(db: Session, school_id: int, audience: list[str]) -> list[User]:
    """Resolve school-scoped users with FCM tokens matching audience roles."""
    normalized = {str(a).strip().lower() for a in audience} or {"all"}
    q = db.query(User).filter(
        User.school_id == school_id,
        User.deleted_at.is_(None),
        User.fcm_id.isnot(None),
        User.fcm_id != "",
    )
    users = list(q.all())
    if "all" in normalized:
        return users

    staff_user_ids = {
        int(s.user_id)
        for s in db.query(Staff).filter(Staff.school_id == school_id).all()
    }
    student_user_ids = {
        int(s.user_id)
        for s in db.query(Student)
        .filter(Student.school_id == school_id, Student.deleted_at.is_(None))
        .all()
    }
    guardian_ids = {
        int(s.guardian_id)
        for s in db.query(Student)
        .filter(
            Student.school_id == school_id,
            Student.deleted_at.is_(None),
            Student.guardian_id.isnot(None),
        )
        .all()
        if s.guardian_id
    }

    out: list[User] = []
    for u in users:
        uid = int(u.id)
        roles: set[str] = set()
        if uid in student_user_ids:
            roles.add("students")
        if uid in guardian_ids:
            roles.add("parents")
        if uid in staff_user_ids:
            roles.add("staff")
            roles.add("teachers")  # staff includes teachers for push fan-out
        if roles & normalized:
            out.append(u)
    return out


def _enqueue(
    db: Session,
    school_id: int,
    *,
    title: str,
    body: str,
    audience: list[str],
    created_by: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    school = db.get(School, school_id)
    if school is None or school.deleted_at is not None:
        raise AcademicError(404, "School not found")

    if idempotency_key:
        existing = (
            db.query(Notification)
            .filter(
                Notification.school_id == school_id,
                Notification.idempotency_key == idempotency_key,
                Notification.deleted_at.is_(None),
            )
            .first()
        )
        if existing is not None:
            return {
                "id": existing.id,
                "title": existing.title,
                "delivery": existing.delivery,
                "audience": audience,
                "idempotent_replay": True,
            }

    now = _now()
    row = Notification(
        title=title[:255],
        body=body,
        status=1,
        school_id=school_id,
        created_by=created_by,
        audience_json=json.dumps(audience),
        delivery="queued",
        recipients=0,
        delivered=0,
        failed=0,
        retry_count=0,
        max_retries=MAX_RETRIES_DEFAULT,
        idempotency_key=idempotency_key[:191] if idempotency_key else None,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return {
        "id": row.id,
        "title": row.title,
        "delivery": row.delivery,
        "audience": audience,
        "idempotent_replay": False,
    }


def enqueue_leave_decision(db: Session, school_id: int, leave: Leave, *, decision: str) -> dict:
    title = f"Leave {decision}"
    body = f"Your leave request ({leave.from_date} to {leave.to_date}) was {decision}."
    return _enqueue(
        db,
        school_id,
        title=title,
        body=body,
        audience=["staff", "teachers"],
        created_by=f"leave:{leave.id}",
        idempotency_key=f"leave:{leave.id}:{decision}",
    )


def enqueue_event(
    db: Session,
    school_id: int,
    *,
    event_type: str,
    title: str,
    body: str,
    audience: list[str] | None = None,
    idempotency_key: str | None = None,
) -> dict:
    key = idempotency_key or f"event:{event_type}:{title[:40]}"
    return _enqueue(
        db,
        school_id,
        title=title,
        body=body,
        audience=audience or ["all"],
        created_by=f"event:{event_type}",
        idempotency_key=key[:191],
    )


def enqueue_student_absence(
    db: Session,
    school_id: int,
    *,
    attendance_id: int,
    student_id: int,
    attendance_date,
) -> dict:
    return enqueue_event(
        db,
        school_id,
        event_type="student_absence",
        title="Student absence",
        body=f"Student #{student_id} marked absent on {attendance_date}.",
        audience=["parents"],
        idempotency_key=f"absence:{school_id}:{attendance_id}",
    )


def enqueue_fee_reminder(
    db: Session,
    school_id: int,
    *,
    assignment_id: int,
    student_id: int,
    amount: float,
) -> dict:
    return enqueue_event(
        db,
        school_id,
        event_type="fee_reminder",
        title="Fee reminder",
        body=f"Outstanding fee balance {amount:.2f} for student #{student_id}.",
        audience=["parents", "students"],
        idempotency_key=f"fee_reminder:{school_id}:{assignment_id}",
    )


def enqueue_exam_announcement(
    db: Session, school_id: int, *, exam_id: int, exam_name: str
) -> dict:
    return enqueue_event(
        db,
        school_id,
        event_type="exam_announcement",
        title=f"Exam: {exam_name[:80]}",
        body=f"Examination '{exam_name}' has been published.",
        audience=["students", "parents"],
        idempotency_key=f"exam_publish:{school_id}:{exam_id}",
    )


def enqueue_exam_results(
    db: Session, school_id: int, *, exam_id: int, exam_name: str
) -> dict:
    return enqueue_event(
        db,
        school_id,
        event_type="exam_results",
        title=f"Results: {exam_name[:80]}",
        body=f"Results for '{exam_name}' are available.",
        audience=["students", "parents"],
        idempotency_key=f"exam_results:{school_id}:{exam_id}",
    )


def attempt_deliver_notification(db: Session, notification_id: int) -> dict[str, Any]:
    """Best-effort FCM delivery with bounded retries and accurate status."""
    row = db.get(Notification, notification_id)
    if row is None or row.deleted_at is not None:
        return {"ok": False, "reason": "not_found"}
    if row.delivery == "cancelled":
        return {"ok": True, "delivery": "cancelled", "id": row.id}
    if row.delivery == "sent":
        return {"ok": True, "delivery": "sent", "id": row.id, "idempotent": True}

    creds = _firebase_creds_from_env()
    if creds is None:
        row.delivery = "queued"
        row.failure_reason = "FCM not configured; notification remains queued"
        row.updated_at = _now()
        _commit(db)
        return {"ok": True, "delivery": "queued", "id": row.id, "reason": "not_configured"}

    max_retries = int(getattr(row, "max_retries", None) or MAX_RETRIES_DEFAULT)
    retry_count = int(getattr(row, "retry_count", None) or 0)
    if retry_count >= max_retries and row.delivery == "failed":
        return {"ok": False, "delivery": "failed", "id": row.id, "reason": "max_retries"}

    audience: list[str] = []
    if row.audience_json:
        try:
            audience = json.loads(row.audience_json) or []
        except (TypeError, ValueError):
            audience = ["all"]

    school_id = int(row.school_id) if row.school_id is not None else 0
    if not school_id:
        row.delivery = "failed"
        row.failure_reason = "Notification missing school_id"
        row.updated_at = _now()
        _commit(db)
        return {"ok": False, "delivery": "failed", "id": row.id}

    targets = _audience_users(db, school_id, audience)
    # Validate school ownership of every token holder.
    tokens = [
        (u.id, u.fcm_id)
        for u in targets
        if u.fcm_id and u.school_id == school_id
    ]
    row.recipients = len(tokens)
    row.last_attempt_at = _now()
    row.retry_count = retry_count + 1
    row.updated_at = row.last_attempt_at

    if not tokens:
        row.delivery = "failed"
        row.failed = 0
        row.delivered = 0
        row.failure_reason = "No eligible FCM tokens for audience in this school"
        _commit(db)
        return {"ok": False, "delivery": "failed", "id": row.id, "recipients": 0}

    try:
        access_token = _google_access_token(creds)
    except Exception as exc:
        logger.exception("fcm_oauth_failed notification_id=%s", notification_id)
        row.delivery = "queued" if row.retry_count < max_retries else "failed"
        row.failure_reason = f"FCM OAuth failed: {exc}"
        _commit(db)
        return {"ok": False, "delivery": row.delivery, "id": row.id, "reason": "oauth"}

    delivered = 0
    failed = 0
    last_error = None
    for _user_id, token in tokens:
        message = {
            "token": token,
            "notification": {"title": row.title, "body": row.body or ""},
        }
        try:
            result = _send_fcm_message(access_token, creds["project_id"], message)
        except Exception as exc:
            failed += 1
            last_error = str(exc)
            logger.exception("fcm_send_error notification_id=%s", notification_id)
            continue
        if result.get("ok"):
            delivered += 1
        else:
            failed += 1
            last_error = json.dumps(result.get("body") or {})[:500]

    row.delivered = delivered
    row.failed = failed
    if delivered > 0 and failed == 0:
        row.delivery = "sent"
        row.failure_reason = None
    elif delivered > 0 and failed > 0:
        row.delivery = "partial"
        row.failure_reason = last_error
    elif row.retry_count < max_retries:
        row.delivery = "queued"
        row.failure_reason = last_error or "All FCM sends failed; will retry"
    else:
        row.delivery = "failed"
        row.failure_reason = last_error or "All FCM sends failed; retries exhausted"

    _commit(db)
    return {
        "ok": row.delivery in ("sent", "partial"),
        "delivery": row.delivery,
        "id": row.id,
        "delivered": delivered,
        "failed": failed,
        "recipients": len(tokens),
    }


def process_queued_for_school(db: Session, school_id: int, *, limit: int = 50) -> dict:
    rows = (
        db.query(Notification)
        .filter(
            Notification.school_id == school_id,
            Notification.deleted_at.is_(None),
            Notification.delivery == "queued",
        )
        .order_by(Notification.id.asc())
        .limit(limit)
        .all()
    )
    results = [attempt_deliver_notification(db, r.id) for r in rows]
    return {"processed": len(results), "results": results}


def schedule_delivery_background(background_tasks, db_factory, notification_id: int) -> None:
    """Enqueue BackgroundTasks job that opens a fresh session for delivery."""

    def _job() -> None:
        db = db_factory()
        try:
            attempt_deliver_notification(db, notification_id)
        except Exception:
            logger.exception("background_delivery_failed notification_id=%s", notification_id)
        finally:
            db.close()

    background_tasks.add_task(_job)


def cancel_notification(db: Session, school_id: int, row_id: int) -> dict:
    row = db.get(Notification, row_id)
    if row is None or row.school_id != school_id or row.deleted_at is not None:
        raise AcademicError(404, "Notification not found")
    if row.delivery == "sent":
        raise AcademicError(409, "Cannot cancel a sent notification")
    row.delivery = "cancelled"
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return {
        "id": row.id,
        "delivery": row.delivery,
        "title": row.title,
        "body": row.body,
        "status": row.status,
        "school_id": row.school_id,
        "audience": json.loads(row.audience_json) if row.audience_json else ["all"],
        "recipients": row.recipients,
        "delivered": row.delivered,
        "failed": row.failed,
        "failure_reason": row.failure_reason,
    }
