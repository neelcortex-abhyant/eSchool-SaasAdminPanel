"""School Admin settings / CMS / support routes (mounted under /school-admin)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_school_permission
from app.core import rate_limit
from app.services.v1 import rbac
from app.services.v1 import school_settings_cms as cms
from app.services.v1.school_academics import AcademicError

router = APIRouter(prefix="", tags=["v1-school-admin-settings"])
public_router = APIRouter(prefix="/public", tags=["v1-public-contact"])

require_settings = require_school_permission(rbac.PERM_SETTINGS)


def _school_id(auth: AuthContext) -> int:
    return int(auth.user.school_id)  # type: ignore[arg-type]


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


# ---- Body models (extra=forbid) ----


class ContentUpsertBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255)
    body: str | None = Field(default=None, max_length=100_000)


class FaqCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, max_length=512)
    answer: str = Field(default="", max_length=100_000)
    sort_order: int | None = 0
    status: int | None = 1


class FaqPatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str | None = Field(default=None, min_length=1, max_length=512)
    answer: str | None = Field(default=None, max_length=100_000)
    sort_order: int | None = None
    status: int | None = None


class LeaveSettingsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: dict[str, Any] | list[Any] | None = None
    notes: str | None = None


class OnlineExamTermsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255)
    body: str | None = Field(default=None, max_length=100_000)


class EmailTemplateCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=1, max_length=64)
    subject: str = Field(..., min_length=1, max_length=255)
    body_text: str = Field(default="")
    body_html: str | None = None
    locale: str = Field(default="en", max_length=16)


class EmailTemplatePatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str | None = Field(default=None, min_length=1, max_length=64)
    subject: str | None = Field(default=None, min_length=1, max_length=255)
    body_text: str | None = None
    body_html: str | None = None
    locale: str | None = Field(default=None, max_length=16)


class IntegrationUpsertBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_config: dict[str, Any] | None = None
    secret: str | None = None
    clear_secret: bool | None = False


class FormFieldCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str = Field(..., min_length=1, max_length=32)
    field_key: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=255)
    field_type: str = Field(..., min_length=1, max_length=32)
    required: int | bool | None = 0
    options: list[Any] | dict[str, Any] | None = None
    sort_order: int | None = 0


class FormFieldPatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str | None = Field(default=None, max_length=32)
    field_key: str | None = Field(default=None, max_length=64)
    label: str | None = Field(default=None, max_length=255)
    field_type: str | None = Field(default=None, max_length=32)
    required: int | bool | None = None
    options: list[Any] | dict[str, Any] | None = None
    sort_order: int | None = None


class ContactInquiryPatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(..., min_length=1, max_length=32)


class SupportTicketCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    priority: str | None = Field(default="normal", max_length=32)
    opener_type: str | None = Field(default="school_admin", max_length=32)
    opener_ref: str | None = Field(default=None, max_length=64)


class SupportTicketPatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, max_length=32)
    priority: str | None = Field(default=None, max_length=32)


class SupportTicketMessageBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(..., min_length=1)
    author_type: str | None = Field(default="school_admin", max_length=32)
    author_ref: str | None = Field(default=None, max_length=64)


class PublicContactBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=64)
    subject: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)


# ---- Phase A: content + FAQ ----


@router.get("/content/{slug}")
def get_content(
    slug: str,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: cms.get_content(db, _school_id(auth), slug))


@router.put("/content/{slug}")
def put_content(
    slug: str,
    body: ContentUpsertBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: cms.put_content(db, _school_id(auth), slug, body.model_dump(exclude_unset=True))
    )


@router.get("/web-content")
def get_web_content(
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: cms.get_web_content(db, _school_id(auth)))


@router.put("/web-content")
def put_web_content(
    body: ContentUpsertBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: cms.put_web_content(db, _school_id(auth), body.model_dump(exclude_unset=True))
    )


@router.get("/faqs")
def list_faqs(
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: cms.list_faqs(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/faqs", status_code=status.HTTP_201_CREATED)
def create_faq(
    body: FaqCreateBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: cms.create_faq(db, _school_id(auth), body.model_dump(exclude_unset=True)))


@router.patch("/faqs/{faq_id}")
def patch_faq(
    faq_id: int,
    body: FaqPatchBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: cms.update_faq(db, _school_id(auth), faq_id, body.model_dump(exclude_unset=True))
    )


@router.delete("/faqs/{faq_id}")
def delete_faq(
    faq_id: int,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: cms.soft_delete_faq(db, _school_id(auth), faq_id))


# ---- Phase B ----


@router.get("/leave-settings")
def get_leave_settings(
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: cms.get_leave_settings(db, _school_id(auth)))


@router.put("/leave-settings")
def put_leave_settings(
    body: LeaveSettingsBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: cms.put_leave_settings(db, _school_id(auth), body.model_dump(exclude_unset=True))
    )


@router.get("/online-exam-terms")
def get_online_exam_terms(
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: cms.get_online_exam_terms(db, _school_id(auth)))


@router.put("/online-exam-terms")
def put_online_exam_terms(
    body: OnlineExamTermsBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: cms.put_online_exam_terms(
            db, _school_id(auth), body.model_dump(exclude_unset=True)
        )
    )


# ---- Phase C ----


@router.get("/email-templates")
def list_email_templates(
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(
        lambda: cms.list_email_templates(db, _school_id(auth), page=page, page_size=page_size)
    )


@router.post("/email-templates", status_code=status.HTTP_201_CREATED)
def create_email_template(
    body: EmailTemplateCreateBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: cms.create_email_template(
            db, _school_id(auth), body.model_dump(exclude_unset=True)
        )
    )


@router.get("/email-templates/{template_id}")
def get_email_template(
    template_id: int,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: cms.get_email_template(db, _school_id(auth), template_id))


@router.patch("/email-templates/{template_id}")
def patch_email_template(
    template_id: int,
    body: EmailTemplatePatchBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: cms.update_email_template(
            db, _school_id(auth), template_id, body.model_dump(exclude_unset=True)
        )
    )


@router.delete("/email-templates/{template_id}")
def delete_email_template(
    template_id: int,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: cms.soft_delete_email_template(db, _school_id(auth), template_id))


# ---- Phase D ----


@router.get("/whatsapp-settings")
def get_whatsapp_settings(
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: cms.get_whatsapp_settings(db, _school_id(auth)))


@router.put("/whatsapp-settings")
def put_whatsapp_settings(
    body: IntegrationUpsertBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: cms.put_whatsapp_settings(
            db, _school_id(auth), body.model_dump(exclude_unset=True)
        )
    )


@router.get("/payment-gateway-settings")
def get_payment_gateway_settings(
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: cms.get_payment_gateway_settings(db, _school_id(auth)))


@router.put("/payment-gateway-settings")
def put_payment_gateway_settings(
    body: IntegrationUpsertBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: cms.put_payment_gateway_settings(
            db, _school_id(auth), body.model_dump(exclude_unset=True)
        )
    )


@router.get("/third-party-integrations")
def list_third_party_integrations(
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: cms.list_third_party_integrations(db, _school_id(auth)))


@router.put("/third-party-integrations/{provider}")
def put_third_party_integration(
    provider: str,
    body: IntegrationUpsertBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: cms.put_third_party_integration(
            db, _school_id(auth), provider, body.model_dump(exclude_unset=True)
        )
    )


# ---- Phase E ----


@router.get("/user-form-fields")
def list_user_form_fields(
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
    entity_type: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(
        lambda: cms.list_form_fields(
            db,
            _school_id(auth),
            entity_type=entity_type,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/user-form-fields", status_code=status.HTTP_201_CREATED)
def create_user_form_field(
    body: FormFieldCreateBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: cms.create_form_field(db, _school_id(auth), body.model_dump(exclude_unset=True))
    )


@router.patch("/user-form-fields/{field_id}")
def patch_user_form_field(
    field_id: int,
    body: FormFieldPatchBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: cms.update_form_field(
            db, _school_id(auth), field_id, body.model_dump(exclude_unset=True)
        )
    )


@router.delete("/user-form-fields/{field_id}")
def delete_user_form_field(
    field_id: int,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: cms.soft_delete_form_field(db, _school_id(auth), field_id))


# ---- Phase F ----


@router.get("/contact-inquiries")
def list_contact_inquiries(
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(
        lambda: cms.list_contact_inquiries(
            db,
            _school_id(auth),
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/contact-inquiries/{inquiry_id}")
def get_contact_inquiry(
    inquiry_id: int,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: cms.get_contact_inquiry(db, _school_id(auth), inquiry_id))


@router.patch("/contact-inquiries/{inquiry_id}")
def patch_contact_inquiry(
    inquiry_id: int,
    body: ContactInquiryPatchBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: cms.patch_contact_inquiry(
            db, _school_id(auth), inquiry_id, body.model_dump(exclude_unset=True)
        )
    )


@router.get("/support-tickets")
def list_support_tickets(
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(
        lambda: cms.list_support_tickets(
            db,
            _school_id(auth),
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/support-tickets", status_code=status.HTTP_201_CREATED)
def create_support_ticket(
    body: SupportTicketCreateBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    payload = body.model_dump(exclude_unset=True)
    if not payload.get("opener_ref"):
        payload["opener_ref"] = str(auth.user.id)
    return _run(lambda: cms.create_support_ticket(db, _school_id(auth), payload))


@router.get("/support-tickets/{ticket_id}")
def get_support_ticket(
    ticket_id: int,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: cms.get_support_ticket(db, _school_id(auth), ticket_id))


@router.patch("/support-tickets/{ticket_id}")
def patch_support_ticket(
    ticket_id: int,
    body: SupportTicketPatchBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: cms.patch_support_ticket(
            db, _school_id(auth), ticket_id, body.model_dump(exclude_unset=True)
        )
    )


@router.post("/support-tickets/{ticket_id}/messages", status_code=status.HTTP_201_CREATED)
def add_support_ticket_message(
    ticket_id: int,
    body: SupportTicketMessageBody,
    auth: Annotated[AuthContext, Depends(require_settings)],
    db: Annotated[Session, Depends(central_db)],
):
    payload = body.model_dump(exclude_unset=True)
    if not payload.get("author_ref"):
        payload["author_ref"] = str(auth.user.id)
    return _run(
        lambda: cms.add_support_ticket_message(db, _school_id(auth), ticket_id, payload)
    )


# ---- Public contact (rate-limited; school resolved by code) ----


@public_router.post(
    "/schools/{code}/contact-inquiries",
    status_code=status.HTTP_201_CREATED,
)
def public_create_contact_inquiry(
    code: str,
    body: PublicContactBody,
    request: Request,
    db: Annotated[Session, Depends(central_db)],
):
    rate_limit.FORGOT_PER_IP.hit(rate_limit.client_ip(request))
    return _run(
        lambda: cms.create_public_contact_inquiry(
            db, code, body.model_dump(exclude_unset=True)
        )
    )
