"""School Admin messaging moderation routes (mounted under /school-admin)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_school_permission
from app.schemas.v1.school_admin_erp_responses import json_response
from app.services.v1 import rbac
from app.services.v1 import school_messaging as messaging
from app.services.v1.school_academics import AcademicError

router = APIRouter(prefix="", tags=["v1-school-admin-messaging"])

require_school = require_school_permission(rbac.PERM_SCHOOL)


def _school_id(auth: AuthContext) -> int:
    return int(auth.user.school_id)  # type: ignore[arg-type]


def _admin_legacy_user_id(db: Session, auth: AuthContext) -> int:
    """School-admin v1 UUID → legacy users.id for messaging FKs / unread."""
    return messaging.resolve_legacy_user_id(
        db, _school_id(auth), email=getattr(auth.user, "email", None)
    )


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


class _Out(BaseModel):
    model_config = ConfigDict(extra="ignore")


class MessagingPolicyOut(_Out):
    id: int | None = None
    school_id: int | None = None
    can_view: bool = True
    can_send: bool = True
    can_moderate: bool = True
    poll_seconds: int = 15
    updated_at: str | None = None


class MessagingPolicyPutBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool | None = None
    can_send: bool | None = None
    can_moderate: bool | None = None
    poll_seconds: int | None = Field(default=None, ge=5, le=300)


class ConversationOut(_Out):
    id: int
    subject: str | None = None
    student_id: int
    student_name: str | None = None
    class_name: str | None = None
    teacher: dict[str, Any] | None = None
    parent: dict[str, Any] | None = None
    last_message: str | None = None
    last_message_at: str | None = None
    unread: int = 0
    flagged: bool = False
    archived_at: str | None = None


class ConversationListOut(_Out):
    items: list[ConversationOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class MessageOut(_Out):
    id: int
    conversation_id: int
    sender: dict[str, Any] | None = None
    body: str
    attachments: list[Any] = Field(default_factory=list)
    sent_at: str | None = None
    hidden: bool = False


class MessageListOut(_Out):
    items: list[MessageOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class MessageCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(..., min_length=1, max_length=2000)


class ConversationCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: int = Field(..., ge=1)
    teacher_user_id: int = Field(..., ge=1)
    parent_user_id: int = Field(..., ge=1)
    subject: str | None = Field(default=None, max_length=255)


class ConversationPatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flagged: bool | None = None
    archived: bool | None = None


class MessagePatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hidden: bool | None = None


class OkReadOut(_Out):
    ok: bool = True
    conversation_id: int
    last_read_at: str | None = None


@router.get("/messaging/policy", responses=json_response(MessagingPolicyOut))
def get_messaging_policy(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: messaging.get_messaging_policy(db, _school_id(auth)))


@router.put("/messaging/policy", responses=json_response(MessagingPolicyOut))
def put_messaging_policy(
    body: MessagingPolicyPutBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: messaging.put_messaging_policy(
            db, _school_id(auth), body.model_dump(exclude_unset=True)
        )
    )


@router.get("/conversations", responses=json_response(ConversationListOut))
def list_conversations(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    q: str | None = Query(default=None),
    unread: bool | None = Query(default=None),
    flagged: bool | None = Query(default=None),
):
    return _run(
        lambda: messaging.list_conversations(
            db,
            _school_id(auth),
            role="admin",
            user_id=_admin_legacy_user_id(db, auth),
            q=q,
            unread=unread,
            flagged=flagged,
            page=page,
            page_size=page_size,
        )
    )


@router.post(
    "/conversations",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(ConversationOut, status_code=201),
)
def create_conversation(
    body: ConversationCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: messaging.create_conversation(
            db,
            _school_id(auth),
            body.model_dump(exclude_unset=True),
            role="admin",
            user_id=_admin_legacy_user_id(db, auth),
        )
    )


@router.get("/conversations/{conversation_id}/messages", responses=json_response(MessageListOut))
def list_messages(
    conversation_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=50),
):
    return _run(
        lambda: messaging.list_messages(
            db,
            _school_id(auth),
            conversation_id,
            role="admin",
            user_id=_admin_legacy_user_id(db, auth),
            page=page,
            page_size=page_size,
        )
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(MessageOut, status_code=201),
)
def send_message(
    conversation_id: int,
    body: MessageCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: messaging.send_message(
            db,
            _school_id(auth),
            conversation_id,
            body.model_dump(),
            role="admin",
            user_id=_admin_legacy_user_id(db, auth),
        )
    )


@router.post("/conversations/{conversation_id}/read", responses=json_response(OkReadOut))
def mark_read(
    conversation_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: messaging.mark_conversation_read(
            db,
            _school_id(auth),
            conversation_id,
            role="admin",
            user_id=_admin_legacy_user_id(db, auth),
        )
    )


@router.patch("/conversations/{conversation_id}", responses=json_response(ConversationOut))
def patch_conversation(
    conversation_id: int,
    body: ConversationPatchBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: messaging.patch_conversation(
            db,
            _school_id(auth),
            conversation_id,
            body.model_dump(exclude_unset=True),
            role="admin",
            user_id=_admin_legacy_user_id(db, auth),
        )
    )


@router.patch("/messages/{message_id}", responses=json_response(MessageOut))
def patch_message(
    message_id: int,
    body: MessagePatchBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: messaging.patch_message(
            db,
            _school_id(auth),
            message_id,
            body.model_dump(exclude_unset=True),
            role="admin",
            user_id=_admin_legacy_user_id(db, auth),
        )
    )
