"""Response models for school-admin settings / CMS / study materials / online assessments."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.v1.school_admin_erp_responses import DeletedOut, json_response

__all__ = [
    "DeletedOut",
    "json_response",
    "ContentPageOut",
    "FaqOut",
    "LeaveSettingsOut",
    "EmailTemplateOut",
    "IntegrationSettingsOut",
    "StudyMaterialOut",
    "OnlineAssessmentOut",
    "OnlineAssessmentChoiceOut",
    "OnlineAssessmentQuestionOut",
    "OnlineAssessmentQuestionsImportOut",
    "OnlineExamTermsOut",
    "UserFormFieldOut",
    "SupportTicketOut",
    "SupportTicketMessageOut",
    "ContactInquiryOut",
    "OkIdOut",
    "StudyMaterialListOut",
    "OnlineAssessmentListOut",
    "ContentPageListOut",
    "FaqListOut",
    "EmailTemplateListOut",
    "UserFormFieldListOut",
    "SupportTicketListOut",
    "ContactInquiryListOut",
    "IntegrationSettingsListOut",
]


class _Out(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ContentPageOut(_Out):
    id: int
    slug: str
    title: str
    body: str = ""
    updated_at: str | None = None
    created_at: str | None = None


class FaqOut(_Out):
    id: int
    question: str
    answer: str = ""
    sort_order: int = 0
    status: int | None = None
    updated_at: str | None = None
    created_at: str | None = None


class LeaveSettingsOut(_Out):
    id: int | None = None
    policy: Any = None
    notes: str | None = None
    updated_at: str | None = None


class EmailTemplateOut(_Out):
    id: int
    key: str
    subject: str | None = None
    body_text: str = ""
    body_html: str | None = None
    locale: str = "en"
    updated_at: str | None = None
    created_at: str | None = None


class IntegrationSettingsOut(_Out):
    """Public integration view — never includes secret ciphertext."""

    provider: str
    public_config: Any = None
    configured: bool = False
    updated_at: str | None = None


class StudyMaterialOut(_Out):
    id: int
    session_year_id: int | None = None
    class_section_id: int | None = None
    subject_id: int | None = None
    subject_name: str | None = None
    teacher_user_id: int | None = None
    teacher_name: str | None = None
    resource_type: str | None = None
    title: str
    description: str | None = None
    chapter: str | None = None
    topic: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    original_filename: str | None = None
    has_file: bool = False
    external_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class OnlineAssessmentOut(_Out):
    id: int
    session_year_id: int
    class_section_id: int
    subject_id: int
    subject_name: str | None = None
    teacher_user_id: int
    teacher_name: str | None = None
    title: str
    instructions: str | None = None
    duration_minutes: int | None = None
    total_marks: float | None = None
    passing_marks: float | None = None
    available_from: str | None = None
    available_until: str | None = None
    status: str | None = None
    results_published: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class OnlineAssessmentChoiceOut(_Out):
    id: int
    choice_text: str
    sort_order: int = 0
    is_correct: bool | None = None


class OnlineAssessmentQuestionOut(_Out):
    id: int
    question_text: str
    topic: str | None = None
    question_type: str | None = None
    marks: float
    sort_order: int = 0
    version: int = 1
    choices: list[OnlineAssessmentChoiceOut | dict[str, Any]] = Field(default_factory=list)


class OnlineAssessmentQuestionsImportOut(_Out):
    created: int
    question_ids: list[int] = Field(default_factory=list)


class OnlineExamTermsOut(_Out):
    id: int | None = None
    title: str = ""
    body: str = ""
    updated_at: str | None = None


class UserFormFieldOut(_Out):
    id: int
    entity_type: str
    field_key: str
    label: str
    field_type: str
    required: int = 0
    options: Any = None
    sort_order: int = 0
    updated_at: str | None = None
    created_at: str | None = None


class SupportTicketOut(_Out):
    id: int
    subject: str
    body: str
    status: str
    priority: str | None = None
    opener_type: str | None = None
    opener_ref: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    messages: list[Any] | None = None


class SupportTicketMessageOut(_Out):
    id: int
    ticket_id: int
    author_type: str | None = None
    author_ref: str | None = None
    body: str
    created_at: str | None = None


class ContactInquiryOut(_Out):
    id: int
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    subject: str | None = None
    message: str | None = None
    status: str | None = None
    source: str | None = None
    updated_at: str | None = None
    created_at: str | None = None


class OkIdOut(_Out):
    """CMS soft-delete shape ``{\"ok\": true, \"id\": ...}``."""

    ok: bool = True
    id: int


class StudyMaterialListOut(_Out):
    items: list[StudyMaterialOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class OnlineAssessmentListOut(_Out):
    items: list[OnlineAssessmentOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class ContentPageListOut(_Out):
    items: list[ContentPageOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class FaqListOut(_Out):
    items: list[FaqOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class EmailTemplateListOut(_Out):
    items: list[EmailTemplateOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class UserFormFieldListOut(_Out):
    items: list[UserFormFieldOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class SupportTicketListOut(_Out):
    items: list[SupportTicketOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class ContactInquiryListOut(_Out):
    items: list[ContactInquiryOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class IntegrationSettingsListOut(_Out):
    items: list[IntegrationSettingsOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class OnlineAssessmentAttemptOut(_Out):
    id: int
    assessment_id: int | None = None
    student_id: int | None = None
    student_name: str | None = None
    admission_no: str | None = None
    status: str | None = None
    started_at: str | None = None
    ends_at: str | None = None
    submitted_at: str | None = None
    assessment_title: str | None = None
    duration_minutes: int | None = None
    total_marks: float | None = None
    results_published: bool | None = None
    score: float | None = None
    percentage: float | None = None
    passed: bool | None = None
    questions: list[Any] | None = None
    answers: list[Any] | None = None


class OnlineAssessmentAttemptListOut(_Out):
    items: list[OnlineAssessmentAttemptOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
