"""Teacher–parent messaging. School Admin moderation via policy. HTTP polling only."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.tables import (
    ClassSection,
    ConversationMessage,
    ConversationRead,
    MessageConversation,
    MessagingPolicy,
    School,
    SchoolClass,
    Section,
    Staff,
    Student,
    StudentGuardian,
    TeacherAssignment,
    User,
)
from app.services.v1.document_storage import (
    discard,
    get_storage,
    sanitize_filename,
    storage_configured,
    validate_study_material_upload,
)
from app.services.v1.school_academics import (
    AcademicError,
    _commit,
    _envelope,
    _now,
    _owned,
    _page,
    _user_name,
)

RoleKind = Literal["admin", "teacher", "parent"]

# Messaging attachments reuse study-material type set (images + PDF + office docs).
_MSG_MAX_ATTACHMENTS = 3


def resolve_legacy_user_id(
    db: Session,
    school_id: int,
    *,
    email: str | None = None,
    fallback_user_id: int | None = None,
    allow_staff_fallback: bool = False,
) -> int:
    """Map a school-admin v1 identity onto a legacy ``users.id`` for messaging FKs."""
    if email:
        row = (
            db.query(User)
            .filter(
                User.school_id == school_id,
                User.email == email,
                User.deleted_at.is_(None),
            )
            .first()
        )
        if row is not None:
            return int(row.id)
    if fallback_user_id is not None:
        fb = db.get(User, int(fallback_user_id))
        if fb is not None and fb.school_id == school_id and fb.deleted_at is None:
            return int(fb.id)
    if allow_staff_fallback:
        staff = db.query(Staff).filter(Staff.school_id == school_id).order_by(Staff.id.asc()).first()
        if staff is not None:
            return int(staff.user_id)
        any_user = (
            db.query(User)
            .filter(User.school_id == school_id, User.deleted_at.is_(None))
            .order_by(User.id.asc())
            .first()
        )
        if any_user is not None:
            return int(any_user.id)
    raise AcademicError(
        422,
        "No school-admin user mapping available for messaging; ensure admin email exists on a school user",
    )


def ensure_school_admin_actor(
    db: Session, school_id: int, *, email: str | None = None
) -> int:
    """Resolve or create a dedicated school-admin legacy user for messaging FKs.

    Never attributes admin actions to an arbitrary teacher/staff member.
    Preference order: email match → school.admin_id → ensure dedicated actor user.
    """
    if email:
        row = (
            db.query(User)
            .filter(
                User.school_id == school_id,
                User.email == email,
                User.deleted_at.is_(None),
            )
            .first()
        )
        if row is not None:
            return int(row.id)

    school = db.get(School, school_id)
    if school is not None and school.admin_id:
        admin_user = db.get(User, int(school.admin_id))
        if (
            admin_user is not None
            and admin_user.deleted_at is None
            and admin_user.school_id == school_id
        ):
            return int(admin_user.id)

    # Dedicated synthetic actor (not a teacher). Stable email per school.
    actor_email = f"school-admin-actor+{school_id}@eschool.internal"
    existing = (
        db.query(User)
        .filter(
            User.school_id == school_id,
            User.email == actor_email,
            User.deleted_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        return int(existing.id)

    from app.core.security import hash_password

    now = _now()
    actor = User(
        first_name="School",
        last_name="Admin",
        email=actor_email,
        password=hash_password(f"locked-actor-{school_id}-{now.timestamp()}"),
        status=1,
        school_id=school_id,
        created_at=now,
        updated_at=now,
    )
    db.add(actor)
    _commit(db)
    db.refresh(actor)
    if school is not None and not school.admin_id:
        school.admin_id = actor.id
        school.updated_at = _now()
        _commit(db)
    return int(actor.id)


def resolve_school_admin_actor(db: Session, school_id: int, *, email: str | None = None) -> int:
    """Safer admin actor — ensures a school-owned non-teacher identity."""
    return ensure_school_admin_actor(db, school_id, email=email)


def _default_policy(school_id: int) -> dict:
    return {
        "school_id": school_id,
        "can_view": True,
        "can_send": True,
        "can_moderate": True,
        "poll_seconds": 15,
    }


def get_or_create_policy(db: Session, school_id: int) -> MessagingPolicy:
    row = (
        db.query(MessagingPolicy)
        .filter(MessagingPolicy.school_id == school_id, MessagingPolicy.deleted_at.is_(None))
        .first()
    )
    if row is None:
        now = _now()
        row = MessagingPolicy(
            school_id=school_id,
            can_view=1,
            can_send=1,
            can_moderate=1,
            poll_seconds=15,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        _commit(db)
        db.refresh(row)
    return row


def policy_item(row: MessagingPolicy | None, school_id: int) -> dict:
    if row is None:
        return _default_policy(school_id)
    return {
        "id": row.id,
        "school_id": row.school_id,
        "can_view": bool(row.can_view),
        "can_send": bool(row.can_send),
        "can_moderate": bool(row.can_moderate),
        "poll_seconds": int(row.poll_seconds or 15),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def get_messaging_policy(db: Session, school_id: int) -> dict:
    return policy_item(get_or_create_policy(db, school_id), school_id)


def put_messaging_policy(db: Session, school_id: int, body: dict) -> dict:
    row = get_or_create_policy(db, school_id)
    if "can_view" in body and body["can_view"] is not None:
        row.can_view = 1 if body["can_view"] else 0
    if "can_send" in body and body["can_send"] is not None:
        row.can_send = 1 if body["can_send"] else 0
    if "can_moderate" in body and body["can_moderate"] is not None:
        row.can_moderate = 1 if body["can_moderate"] else 0
    if "poll_seconds" in body and body["poll_seconds"] is not None:
        row.poll_seconds = int(body["poll_seconds"])
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return policy_item(row, school_id)


def _require_policy(
    db: Session, school_id: int, *, view: bool = False, send: bool = False, moderate: bool = False
) -> MessagingPolicy:
    row = get_or_create_policy(db, school_id)
    if view and not row.can_view:
        raise AcademicError(403, "Messaging view is disabled by school policy")
    if send and not row.can_send:
        raise AcademicError(403, "Messaging send is disabled by school policy")
    if moderate and not row.can_moderate:
        raise AcademicError(403, "Messaging moderation is disabled by school policy")
    return row


def _party(user: User | None, role: str) -> dict | None:
    if user is None:
        return None
    return {"user_id": user.id, "name": _user_name(user), "role": role}


def _class_label(db: Session, class_section_id: int | None) -> str | None:
    if class_section_id is None:
        return None
    cs = db.get(ClassSection, class_section_id)
    if cs is None:
        return None
    klass = db.get(SchoolClass, cs.class_id)
    section = db.get(Section, cs.section_id) if cs.section_id else None
    parts = [klass.name if klass else None, section.name if section else None]
    return " ".join(p for p in parts if p) or None


def _unread_count(
    db: Session, conversation_id: int, user_id: int, last_message_at: datetime | None
) -> int:
    if last_message_at is None:
        return 0
    read = (
        db.query(ConversationRead)
        .filter(
            ConversationRead.conversation_id == conversation_id,
            ConversationRead.user_id == user_id,
        )
        .first()
    )
    since = read.last_read_at if read else None
    q = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == conversation_id,
        ConversationMessage.deleted_at.is_(None),
        ConversationMessage.hidden == 0,
        ConversationMessage.sender_user_id != user_id,
    )
    if since is not None:
        q = q.filter(ConversationMessage.created_at > since)
    return q.count()


def _conversation_item(db: Session, row: MessageConversation, viewer_user_id: int | None) -> dict:
    student = db.get(Student, row.student_id)
    teacher = db.get(User, row.teacher_user_id)
    parent = db.get(User, row.parent_user_id)
    unread = (
        _unread_count(db, row.id, viewer_user_id, row.last_message_at) if viewer_user_id else 0
    )
    return {
        "id": row.id,
        "subject": row.subject,
        "student_id": row.student_id,
        "student_name": _user_name(db.get(User, student.user_id)) if student else None,
        "class_name": _class_label(db, student.class_section_id if student else None),
        "teacher": _party(teacher, "teacher"),
        "parent": _party(parent, "parent"),
        "last_message": row.last_message_preview,
        "last_message_at": row.last_message_at.isoformat() if row.last_message_at else None,
        "unread": unread,
        "flagged": bool(row.flagged),
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
    }


def _teacher_teaches_student(
    db: Session, school_id: int, teacher_user_id: int, student: Student
) -> bool:
    if student.class_section_id is None:
        return False
    return (
        db.query(TeacherAssignment)
        .filter(
            TeacherAssignment.school_id == school_id,
            TeacherAssignment.teacher_user_id == teacher_user_id,
            TeacherAssignment.class_section_id == student.class_section_id,
            TeacherAssignment.deleted_at.is_(None),
        )
        .first()
        is not None
    )


def _parent_linked(db: Session, school_id: int, parent_user_id: int, student_id: int) -> bool:
    student = db.get(Student, student_id)
    if student is None or student.school_id != school_id or student.deleted_at is not None:
        return False
    if student.guardian_id == parent_user_id:
        return True
    link = (
        db.query(StudentGuardian)
        .filter(
            StudentGuardian.school_id == school_id,
            StudentGuardian.student_id == student_id,
            StudentGuardian.guardian_user_id == parent_user_id,
            StudentGuardian.deleted_at.is_(None),
        )
        .first()
    )
    return link is not None


def _assert_access(
    db: Session,
    school_id: int,
    row: MessageConversation,
    *,
    role: RoleKind,
    user_id: int,
) -> None:
    if row.school_id != school_id or row.deleted_at is not None:
        raise AcademicError(404, "Conversation not found")
    if role == "admin":
        return
    if role == "teacher" and row.teacher_user_id == user_id:
        return
    if role == "parent" and row.parent_user_id == user_id:
        return
    raise AcademicError(404, "Conversation not found")


def list_conversations(
    db: Session,
    school_id: int,
    *,
    role: RoleKind,
    user_id: int,
    q: str | None = None,
    unread: bool | None = None,
    flagged: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    if role == "admin":
        _require_policy(db, school_id, view=True)
    page, page_size = _page(page, page_size)
    query = db.query(MessageConversation).filter(
        MessageConversation.school_id == school_id,
        MessageConversation.deleted_at.is_(None),
    )
    if role == "teacher":
        query = query.filter(MessageConversation.teacher_user_id == user_id)
    elif role == "parent":
        query = query.filter(MessageConversation.parent_user_id == user_id)
    if flagged is True:
        query = query.filter(MessageConversation.flagged == 1)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(MessageConversation.subject.ilike(like))
    rows = query.order_by(MessageConversation.id.desc()).all()
    items = [_conversation_item(db, r, user_id) for r in rows]
    if unread is True:
        items = [i for i in items if i["unread"] > 0]
    elif unread is False:
        items = [i for i in items if i["unread"] == 0]
    total = len(items)
    slice_items = items[(page - 1) * page_size : (page - 1) * page_size + page_size]
    return _envelope(slice_items, total, page, page_size)


def create_conversation(
    db: Session,
    school_id: int,
    body: dict,
    *,
    role: RoleKind,
    user_id: int,
) -> dict:
    if role == "admin":
        _require_policy(db, school_id, send=True)
    student_id = int(body.get("student_id") or 0)
    teacher_user_id = body.get("teacher_user_id")
    parent_user_id = body.get("parent_user_id")
    subject = body.get("subject")
    if not student_id:
        raise AcademicError(422, "student_id is required")
    student = _owned(db, Student, student_id, school_id)
    if role == "teacher":
        teacher_user_id = user_id
    if role == "parent":
        parent_user_id = user_id
    if not teacher_user_id or not parent_user_id:
        raise AcademicError(422, "teacher_user_id and parent_user_id are required")
    teacher_user_id = int(teacher_user_id)
    parent_user_id = int(parent_user_id)
    if not _teacher_teaches_student(db, school_id, teacher_user_id, student):
        raise AcademicError(422, "Teacher is not assigned to this student's class")
    if not _parent_linked(db, school_id, parent_user_id, student_id):
        raise AcademicError(422, "Parent is not linked to this student")

    existing = (
        db.query(MessageConversation)
        .filter(
            MessageConversation.school_id == school_id,
            MessageConversation.student_id == student_id,
            MessageConversation.teacher_user_id == teacher_user_id,
            MessageConversation.parent_user_id == parent_user_id,
            MessageConversation.deleted_at.is_(None),
        )
        .first()
    )
    if existing:
        return _conversation_item(db, existing, user_id)

    now = _now()
    row = MessageConversation(
        school_id=school_id,
        student_id=student_id,
        teacher_user_id=int(teacher_user_id),
        parent_user_id=int(parent_user_id),
        subject=subject[:255] if subject else None,
        flagged=0,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _conversation_item(db, row, user_id)


def _attachment_public(item: dict[str, Any], *, message_id: int | None = None) -> dict[str, Any]:
    """Serialize attachment metadata with additive client aliases (no raw storage URLs)."""
    from urllib.parse import quote

    name = item.get("original_filename")
    size = item.get("size_bytes")
    key = item.get("storage_key")
    out: dict[str, Any] = {
        "original_filename": name,
        "content_type": item.get("content_type"),
        "size_bytes": size,
        "storage_key": key,
        # Additive aliases — existing keys preserved.
        "name": name,
        "size": size,
    }
    if message_id is not None and key:
        out["download_path"] = (
            f"/api/v1/school-admin/messages/{int(message_id)}/attachments"
            f"?storage_key={quote(str(key), safe='')}"
        )
    return out


def _parse_attachments(raw: str | None, *, message_id: int | None = None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        out.append(_attachment_public(item, message_id=message_id))
    return out


def _validate_attachments_meta(raw, *, school_id: int, uploader_user_id: int) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise AcademicError(422, "attachments must be a list")
    if not raw:
        return []
    if not storage_configured():
        raise AcademicError(503, "Document storage is not configured; attachments unavailable")
    if len(raw) > _MSG_MAX_ATTACHMENTS:
        raise AcademicError(422, f"At most {_MSG_MAX_ATTACHMENTS} attachments allowed")
    out: list[dict[str, Any]] = []
    prefix = f"{int(school_id)}/{int(uploader_user_id)}/"
    for item in raw:
        if not isinstance(item, dict):
            raise AcademicError(422, "Each attachment must be an object")
        filename = str(item.get("original_filename") or "").strip()
        storage_key = str(item.get("storage_key") or "").strip()
        if not filename or not storage_key:
            raise AcademicError(422, "attachment requires original_filename and storage_key from upload")
        if storage_key.startswith("http://") or storage_key.startswith("https://"):
            raise AcademicError(422, "attachment storage_key must not be a URL")
        if ".." in storage_key or not storage_key.startswith(prefix):
            raise AcademicError(422, "attachment storage_key is not owned by this school/user")
        out.append(
            {
                "original_filename": filename[:255],
                "content_type": str(item.get("content_type") or "application/octet-stream")[:128],
                "size_bytes": int(item.get("size_bytes") or 0),
                "storage_key": storage_key[:512],
            }
        )
    return out


def upload_message_attachment(
    db: Session,
    school_id: int,
    *,
    role: RoleKind,
    user_id: int,
    data: bytes,
    filename: str | None,
) -> dict:
    """Store a binary attachment; returns metadata to include when sending a message."""
    if role == "admin":
        _require_policy(db, school_id, send=True)
    if not storage_configured():
        raise AcademicError(503, "Document storage is not configured; attachments unavailable")
    content_type, ext, safe_name = validate_study_material_upload(data, claimed_filename=filename)
    storage = get_storage()
    key = storage.build_key(school_id, user_id, ext)
    try:
        storage.put(key, data)
    except Exception:
        discard(storage, key)
        raise
    meta = {
        "original_filename": safe_name or sanitize_filename(filename) or f"file.{ext}",
        "content_type": content_type,
        "size_bytes": len(data),
        "storage_key": key,
    }
    return _attachment_public(meta)


def download_message_attachment(
    db: Session,
    school_id: int,
    message_id: int,
    storage_key: str,
    *,
    role: RoleKind,
    user_id: int,
) -> tuple[bytes, str, str]:
    """Return (bytes, content_type, filename) after access checks."""
    msg = db.get(ConversationMessage, message_id)
    if msg is None or msg.school_id != school_id or msg.deleted_at is not None:
        raise AcademicError(404, "Message not found")
    conv = db.get(MessageConversation, msg.conversation_id)
    if conv is None:
        raise AcademicError(404, "Conversation not found")
    _assert_access(db, school_id, conv, role=role, user_id=user_id)
    attachments = _parse_attachments(getattr(msg, "attachments_json", None))
    match = next((a for a in attachments if a.get("storage_key") == storage_key), None)
    if match is None:
        raise AcademicError(404, "Attachment not found on message")
    if not storage_configured():
        raise AcademicError(503, "Document storage is not configured")
    storage = get_storage()
    payload = storage.get(storage_key)
    return (
        payload,
        str(match.get("content_type") or "application/octet-stream"),
        str(match.get("original_filename") or "attachment"),
    )


def _message_item(db: Session, row: ConversationMessage, *, can_see_hidden: bool) -> dict:
    sender = db.get(User, row.sender_user_id)
    hidden = bool(row.hidden)
    body = row.body
    if hidden and not can_see_hidden:
        body = "[hidden]"
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "sender": _party(sender, "user"),
        "body": body,
        "attachments": _parse_attachments(
            getattr(row, "attachments_json", None), message_id=row.id
        ),
        "sent_at": row.created_at.isoformat() if row.created_at else None,
        "hidden": hidden,
    }


def list_messages(
    db: Session,
    school_id: int,
    conversation_id: int,
    *,
    role: RoleKind,
    user_id: int,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    if role == "admin":
        _require_policy(db, school_id, view=True)
    conv = db.get(MessageConversation, conversation_id)
    if conv is None:
        raise AcademicError(404, "Conversation not found")
    _assert_access(db, school_id, conv, role=role, user_id=user_id)
    page, page_size = _page(page, page_size)
    can_mod = role == "admin" and bool(get_or_create_policy(db, school_id).can_moderate)
    query = db.query(ConversationMessage).filter(
        ConversationMessage.school_id == school_id,
        ConversationMessage.conversation_id == conversation_id,
        ConversationMessage.deleted_at.is_(None),
    )
    if not can_mod:
        query = query.filter(ConversationMessage.hidden == 0)
    total = query.count()
    rows = query.order_by(ConversationMessage.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([_message_item(db, r, can_see_hidden=can_mod) for r in rows], total, page, page_size)


def send_message(
    db: Session,
    school_id: int,
    conversation_id: int,
    body: dict,
    *,
    role: RoleKind,
    user_id: int,
) -> dict:
    _require_policy(db, school_id, send=True) if role == "admin" else None
    conv = db.get(MessageConversation, conversation_id)
    if conv is None:
        raise AcademicError(404, "Conversation not found")
    _assert_access(db, school_id, conv, role=role, user_id=user_id)
    text = str(body.get("body") or "").strip()
    if not text:
        raise AcademicError(422, "body is required")
    if len(text) > 2000:
        raise AcademicError(422, "body must be at most 2000 characters")
    attachments = _validate_attachments_meta(
        body.get("attachments"), school_id=school_id, uploader_user_id=int(user_id)
    )
    sender_id = int(user_id)
    now = _now()
    msg = ConversationMessage(
        school_id=school_id,
        conversation_id=conversation_id,
        sender_user_id=sender_id,
        body=text,
        attachments_json=json.dumps(attachments) if attachments else None,
        hidden=0,
        created_at=now,
        updated_at=now,
    )
    db.add(msg)
    conv.last_message_at = now
    conv.last_message_preview = text[:255]
    conv.updated_at = now
    _commit(db)
    db.refresh(msg)
    item = _message_item(db, msg, can_see_hidden=True)
    if role == "admin":
        item["sender"] = {"user_id": sender_id, "name": "School Admin", "role": "school"}
    return item


def unread_count(
    db: Session,
    school_id: int,
    *,
    role: RoleKind,
    user_id: int,
) -> dict:
    if role == "admin":
        _require_policy(db, school_id, view=True)
        convs = (
            db.query(MessageConversation)
            .filter(
                MessageConversation.school_id == school_id,
                MessageConversation.deleted_at.is_(None),
            )
            .all()
        )
    elif role == "teacher":
        convs = (
            db.query(MessageConversation)
            .filter(
                MessageConversation.school_id == school_id,
                MessageConversation.teacher_user_id == user_id,
                MessageConversation.deleted_at.is_(None),
            )
            .all()
        )
    else:
        convs = (
            db.query(MessageConversation)
            .filter(
                MessageConversation.school_id == school_id,
                MessageConversation.parent_user_id == user_id,
                MessageConversation.deleted_at.is_(None),
            )
            .all()
        )
    total = 0
    by_conversation: list[dict[str, int]] = []
    for conv in convs:
        n = _unread_count(db, conv.id, user_id, conv.last_message_at)
        if n:
            total += n
            by_conversation.append({"conversation_id": conv.id, "unread": n})
    return {"unread": total, "conversations": by_conversation}


def mark_conversation_read(
    db: Session,
    school_id: int,
    conversation_id: int,
    *,
    role: RoleKind,
    user_id: int,
) -> dict:
    conv = db.get(MessageConversation, conversation_id)
    if conv is None:
        raise AcademicError(404, "Conversation not found")
    _assert_access(db, school_id, conv, role=role, user_id=user_id)
    now = _now()
    row = (
        db.query(ConversationRead)
        .filter(
            ConversationRead.conversation_id == conversation_id,
            ConversationRead.user_id == user_id,
        )
        .first()
    )
    if row is None:
        row = ConversationRead(
            school_id=school_id,
            conversation_id=conversation_id,
            user_id=user_id,
            last_read_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.last_read_at = now
        row.updated_at = now
    _commit(db)
    return {"ok": True, "conversation_id": conversation_id, "last_read_at": now.isoformat()}


def patch_conversation(
    db: Session,
    school_id: int,
    conversation_id: int,
    body: dict,
    *,
    role: RoleKind,
    user_id: int,
) -> dict:
    if role != "admin":
        raise AcademicError(403, "Only school admins can moderate conversations")
    _require_policy(db, school_id, moderate=True)
    conv = db.get(MessageConversation, conversation_id)
    if conv is None or conv.school_id != school_id or conv.deleted_at is not None:
        raise AcademicError(404, "Conversation not found")
    if "flagged" in body and body["flagged"] is not None:
        conv.flagged = 1 if body["flagged"] else 0
    if "archived" in body and body["archived"] is not None:
        conv.archived_at = _now() if body["archived"] else None
    conv.updated_at = _now()
    _commit(db)
    db.refresh(conv)
    return _conversation_item(db, conv, user_id)


def patch_message(
    db: Session,
    school_id: int,
    message_id: int,
    body: dict,
    *,
    role: RoleKind,
    user_id: int,
) -> dict:
    if role != "admin":
        raise AcademicError(403, "Only school admins can hide messages")
    _require_policy(db, school_id, moderate=True)
    msg = db.get(ConversationMessage, message_id)
    if msg is None or msg.school_id != school_id or msg.deleted_at is not None:
        raise AcademicError(404, "Message not found")
    if "hidden" in body and body["hidden"] is not None:
        msg.hidden = 1 if body["hidden"] else 0
    msg.updated_at = _now()
    _commit(db)
    db.refresh(msg)
    return _message_item(db, msg, can_see_hidden=True)
