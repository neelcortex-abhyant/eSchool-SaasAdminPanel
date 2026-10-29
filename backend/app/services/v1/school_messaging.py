"""Teacher–parent messaging (text-only v1). School Admin moderation via policy."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.models.tables import (
    ClassSection,
    ConversationMessage,
    ConversationRead,
    MessageConversation,
    MessagingPolicy,
    SchoolClass,
    Section,
    Staff,
    Student,
    StudentGuardian,
    TeacherAssignment,
    User,
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


def resolve_legacy_user_id(db: Session, school_id: int, *, email: str | None = None, fallback_user_id: int | None = None) -> int:
    """Map a school-admin v1 identity onto a legacy ``users.id`` for messaging FKs.

    Prefers same-school user by email; otherwise ``fallback_user_id`` (e.g. conversation teacher).
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
    if fallback_user_id is not None:
        return int(fallback_user_id)
    staff = db.query(Staff).filter(Staff.school_id == school_id).order_by(Staff.id.asc()).first()
    if staff is not None:
        return int(staff.user_id)
    any_user = (
        db.query(User)
        .filter(User.school_id == school_id, User.deleted_at.is_(None))
        .order_by(User.id.asc())
        .first()
    )
    if any_user is None:
        raise AcademicError(422, "No school user available to attribute messaging actions")
    return int(any_user.id)


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
        "school_id": school_id,
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
        secs = int(body["poll_seconds"])
        if secs < 5 or secs > 300:
            raise AcademicError(422, "poll_seconds must be between 5 and 300")
        row.poll_seconds = secs
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return policy_item(row, school_id)


def _require_policy(db: Session, school_id: int, *, view: bool = False, send: bool = False, moderate: bool = False) -> MessagingPolicy:
    row = get_or_create_policy(db, school_id)
    if view and not row.can_view:
        raise AcademicError(403, "Messaging view is disabled by school policy")
    if send and not row.can_send:
        raise AcademicError(403, "Messaging send is disabled by school policy")
    if moderate and not row.can_moderate:
        raise AcademicError(403, "Messaging moderation is disabled by school policy")
    return row


def _class_label(db: Session, class_section_id: int | None) -> str | None:
    if not class_section_id:
        return None
    cs = db.get(ClassSection, class_section_id)
    if cs is None:
        return None
    cls = db.get(SchoolClass, cs.class_id) if cs.class_id else None
    sec = db.get(Section, cs.section_id) if cs.section_id else None
    parts = []
    if cls:
        parts.append(cls.name)
    if sec:
        parts.append(sec.name)
    return " ".join(parts) if parts else None


def _party(user: User | None, role: str) -> dict:
    return {
        "user_id": user.id if user else None,
        "name": _user_name(user) if user else None,
        "role": role,
    }


def _unread_count(db: Session, conversation_id: int, user_id: int, last_message_at: datetime | None) -> int:
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
    q = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == conversation_id,
        ConversationMessage.deleted_at.is_(None),
        ConversationMessage.hidden == 0,
        ConversationMessage.sender_user_id != user_id,
    )
    if read and read.last_read_at:
        q = q.filter(ConversationMessage.created_at > read.last_read_at)
    return q.count()


def _conversation_item(db: Session, row: MessageConversation, viewer_user_id: int | None) -> dict:
    student = db.get(Student, row.student_id)
    teacher = db.get(User, row.teacher_user_id)
    parent = db.get(User, row.parent_user_id)
    unread = _unread_count(db, row.id, viewer_user_id, row.last_message_at) if viewer_user_id else 0
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


def _teacher_teaches_student(db: Session, school_id: int, teacher_user_id: int, student: Student) -> bool:
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
    rows = query.order_by(
        MessageConversation.last_message_at.desc().nulls_last(),
        MessageConversation.id.desc(),
    ).all()
    items = [_conversation_item(db, r, user_id) for r in rows]
    if unread is True:
        items = [i for i in items if i["unread"] > 0]
    elif unread is False:
        items = [i for i in items if i["unread"] == 0]
    total = len(items)
    start = (page - 1) * page_size
    return _envelope(items[start : start + page_size], total, page, page_size)


def create_conversation(
    db: Session,
    school_id: int,
    body: dict,
    *,
    role: RoleKind,
    user_id: int,
) -> dict:
    _require_policy(db, school_id, send=True)
    student_id = int(body.get("student_id") or 0)
    if not student_id:
        raise AcademicError(422, "student_id is required")
    student = _owned(db, Student, student_id, school_id)
    teacher_user_id = int(body.get("teacher_user_id") or 0) or None
    parent_user_id = int(body.get("parent_user_id") or 0) or None
    subject = str(body.get("subject") or "").strip() or None

    if role == "teacher":
        teacher_user_id = user_id
        if parent_user_id is None:
            parent_user_id = student.guardian_id
        if not _teacher_teaches_student(db, school_id, teacher_user_id, student):
            raise AcademicError(404, "Student not found")
        if not _parent_linked(db, school_id, parent_user_id, student_id):
            raise AcademicError(404, "Parent not found")
    elif role == "parent":
        parent_user_id = user_id
        if teacher_user_id is None:
            raise AcademicError(422, "teacher_user_id is required")
        if not _parent_linked(db, school_id, parent_user_id, student_id):
            raise AcademicError(404, "Student not found")
        if not _teacher_teaches_student(db, school_id, teacher_user_id, student):
            raise AcademicError(404, "Teacher not found")
    else:
        if teacher_user_id is None or parent_user_id is None:
            raise AcademicError(422, "teacher_user_id and parent_user_id are required")
        staff = (
            db.query(Staff)
            .filter(Staff.school_id == school_id, Staff.user_id == teacher_user_id)
            .first()
        )
        if staff is None:
            raise AcademicError(404, "Teacher not found")
        if not _parent_linked(db, school_id, parent_user_id, student_id):
            raise AcademicError(404, "Parent not found")

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
        "attachments": [],
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
    _require_policy(db, school_id, send=True)
    conv = db.get(MessageConversation, conversation_id)
    if conv is None:
        raise AcademicError(404, "Conversation not found")
    _assert_access(db, school_id, conv, role=role, user_id=user_id)
    text = str(body.get("body") or "").strip()
    if not text:
        raise AcademicError(422, "body is required")
    if len(text) > 2000:
        raise AcademicError(422, "body must be at most 2000 characters")
    sender_id = user_id
    if role == "admin":
        # Admin v1 UUID is not a legacy users.id; attribute as school via teacher party.
        sender_id = resolve_legacy_user_id(
            db, school_id, fallback_user_id=conv.teacher_user_id
        )
    now = _now()
    msg = ConversationMessage(
        school_id=school_id,
        conversation_id=conversation_id,
        sender_user_id=sender_id,
        body=text,
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
