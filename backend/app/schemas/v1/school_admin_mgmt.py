"""Typed request bodies for Academic Management wave routes (OpenAPI-accurate).

Fields are derived from ``school_academic_mgmt`` / staff import handlers.
``extra=ignore`` preserves FE compatibility (unknown keys dropped, not 422).
"""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime as DateTime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class _MgmtBase(BaseModel):
    model_config = ConfigDict(extra="ignore")


def dump_mgmt_body(body: BaseModel) -> dict[str, Any]:
    return body.model_dump(exclude_unset=True)


# ---- Question bank ----


class QuestionBankChoiceIn(_MgmtBase):
    choice_text: str = Field(..., min_length=1)
    is_correct: bool | int | str = False


class QuestionBankCreateBody(_MgmtBase):
    question_text: str = Field(..., min_length=1)
    marks: float = Field(..., gt=0)
    subject_id: int | None = Field(default=None, ge=1)
    topic: str | None = Field(default=None, max_length=255)
    choices: list[QuestionBankChoiceIn] = Field(..., min_length=2, max_length=8)


class QuestionBankPatchBody(_MgmtBase):
    question_text: str | None = Field(default=None, min_length=1)
    marks: float | None = Field(default=None, gt=0)
    subject_id: int | None = Field(default=None, ge=1)
    topic: str | None = Field(default=None, max_length=255)
    choices: list[QuestionBankChoiceIn] | None = Field(default=None, min_length=2, max_length=8)


class CopyFromBankBody(_MgmtBase):
    question_ids: list[int] = Field(..., min_length=1)


# ---- Admission / holidays ----


class AdmissionInquiryCreateBody(_MgmtBase):
    student_name: str = Field(..., min_length=1)
    parent_name: str | None = None
    email: EmailStr | None = None
    mobile: str | None = None
    class_interested: str | None = None
    message: str | None = None
    status: str = "open"


class AdmissionInquiryPatchBody(_MgmtBase):
    student_name: str | None = Field(default=None, min_length=1)
    parent_name: str | None = None
    email: EmailStr | None = None
    mobile: str | None = None
    class_interested: str | None = None
    message: str | None = None
    status: str | None = None


class HolidayCreateBody(_MgmtBase):
    title: str = Field(..., min_length=1)
    holiday_date: Date | None = None
    date: Date | None = Field(default=None, description="Alias for holiday_date")
    end_date: Date | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _require_date(self) -> HolidayCreateBody:
        if self.holiday_date is None and self.date is None:
            raise ValueError("holiday_date is required")
        return self


class HolidayPatchBody(_MgmtBase):
    title: str | None = Field(default=None, min_length=1)
    holiday_date: Date | None = None
    date: Date | None = None
    end_date: Date | None = None
    description: str | None = None


# ---- Students extras ----


class StudentImportRowIn(_MgmtBase):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    email: EmailStr
    admission_no: str = Field(..., min_length=1)
    class_section_id: int = Field(..., ge=1)
    session_year_id: int = Field(..., ge=1)
    guardian_id: int = Field(..., ge=1)
    admission_date: Date
    roll_number: int | None = None
    password: str | None = Field(default=None, min_length=8)


class StudentsImportBody(_MgmtBase):
    rows: list[StudentImportRowIn] | None = None
    students: list[StudentImportRowIn] | None = None
    items: list[StudentImportRowIn] | None = None

    @model_validator(mode="after")
    def _require_rows(self) -> StudentsImportBody:
        if not (self.rows or self.students or self.items):
            raise ValueError("rows (or students/items) must be a non-empty list")
        return self

    def row_list(self) -> list[dict[str, Any]]:
        rows = self.rows or self.students or self.items or []
        return [r.model_dump(exclude_unset=True) for r in rows]


class StudentsPromoteBody(_MgmtBase):
    student_ids: list[int] = Field(..., min_length=1)
    to_class_section_id: int = Field(..., ge=1)
    to_session_year_id: int | None = Field(default=None, ge=1)


class StudentTransferBody(_MgmtBase):
    transfer_date: Date | None = None
    to_school_name: str | None = None
    reason: str | None = None


class StudentResetPasswordBody(_MgmtBase):
    password: str = Field(..., min_length=8)


class StudentElectiveCreateBody(_MgmtBase):
    subject_id: int = Field(..., ge=1)
    session_year_id: int = Field(..., ge=1)


# ---- Semesters / streams / shifts / syllabi / online classes ----


class SemesterCreateBody(_MgmtBase):
    name: str = Field(..., min_length=1)
    session_year_id: int = Field(..., ge=1)
    start_date: Date | None = None
    end_date: Date | None = None


class SemesterPatchBody(_MgmtBase):
    name: str | None = Field(default=None, min_length=1)
    start_date: Date | None = None
    end_date: Date | None = None


class StreamCreateBody(_MgmtBase):
    name: str = Field(..., min_length=1)
    description: str | None = None


class StreamPatchBody(_MgmtBase):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None


class ShiftCreateBody(_MgmtBase):
    name: str = Field(..., min_length=1)
    start_time: str | None = Field(default=None, description="HH:MM or HH:MM:SS")
    end_time: str | None = Field(default=None, description="HH:MM or HH:MM:SS")


class ShiftPatchBody(_MgmtBase):
    name: str | None = Field(default=None, min_length=1)
    start_time: str | None = None
    end_time: str | None = None


class SyllabusCreateBody(_MgmtBase):
    title: str = Field(..., min_length=1)
    class_id: int | None = Field(default=None, ge=1)
    subject_id: int | None = Field(default=None, ge=1)
    session_year_id: int | None = Field(default=None, ge=1)
    content: str | None = None


class SyllabusPatchBody(_MgmtBase):
    title: str | None = Field(default=None, min_length=1)
    content: str | None = None


class OnlineClassCreateBody(_MgmtBase):
    title: str = Field(..., min_length=1)
    class_section_id: int | None = Field(default=None, ge=1)
    subject_id: int | None = Field(default=None, ge=1)
    teacher_user_id: int | None = Field(default=None, ge=1)
    meeting_url: str | None = None
    scheduled_at: DateTime | None = None
    duration_minutes: int | None = Field(default=None, ge=1)


class OnlineClassPatchBody(_MgmtBase):
    title: str | None = Field(default=None, min_length=1)
    meeting_url: str | None = None
    scheduled_at: DateTime | None = None
    duration_minutes: int | None = Field(default=None, ge=1)


# ---- Staff import / roles / attendance / tasks ----


class StaffImportRowIn(_MgmtBase):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=8)
    mobile: str | None = None
    employee_id: str | None = None
    employee_code: str | None = Field(default=None, description="Alias for employee_id")
    joining_date: Date | None = None
    employment_status: str | None = None
    employment_type: str | None = Field(default=None, description="Alias when it matches a known status")
    department: str | None = None
    designation: str | None = None
    qualification: str | None = None
    salary: float | None = Field(default=None, ge=0)


class StaffImportBody(_MgmtBase):
    rows: list[StaffImportRowIn] | None = None
    items: list[StaffImportRowIn] | None = None

    @model_validator(mode="after")
    def _require_rows(self) -> StaffImportBody:
        if not (self.rows or self.items):
            raise ValueError("rows (or items) must be a non-empty list")
        return self

    def row_list(self) -> list[dict[str, Any]]:
        rows = self.rows or self.items or []
        return [r.model_dump(exclude_unset=True) for r in rows]


class StaffRolesPutBody(_MgmtBase):
    roles: list[str] = Field(..., min_length=1)


class StaffAttendanceMarkBody(_MgmtBase):
    staff_id: int = Field(..., ge=1)
    attendance_date: Date | None = None
    date: Date | None = Field(default=None, description="Alias for attendance_date")
    status: str = "present"
    check_in: str | None = None
    check_out: str | None = None
    remark: str | None = None


class StaffQrSettingsPutBody(_MgmtBase):
    enabled: bool | int | str = 0
    token: str | None = None


class StaffTaskCreateBody(_MgmtBase):
    title: str = Field(..., min_length=1)
    description: str | None = None
    assigned_to_staff_id: int | None = Field(default=None, ge=1)
    due_date: Date | None = None
    status: str = "open"


class StaffTaskPatchBody(_MgmtBase):
    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    assigned_to_staff_id: int | None = Field(default=None, ge=1)
    due_date: Date | None = None
    status: str | None = None


# ---- Expense / income / payroll ----


class NamedCategoryCreateBody(_MgmtBase):
    name: str = Field(..., min_length=1)
    description: str | None = None


class NamedCategoryPatchBody(_MgmtBase):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None


class IncomeCreateBody(_MgmtBase):
    title: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    category_id: int | None = Field(default=None, ge=1)
    income_date: Date | None = None
    date: Date | None = Field(default=None, description="Alias for income_date")
    session_year_id: int | None = Field(default=None, ge=1)


class IncomePatchBody(_MgmtBase):
    title: str | None = Field(default=None, min_length=1)
    amount: float | None = Field(default=None, gt=0)
    income_date: Date | None = None
    date: Date | None = None


class PayrollSettingsPutBody(_MgmtBase):
    pay_day: int | None = Field(default=None, ge=1, le=28)
    currency: str | None = Field(default=None, max_length=16)
    notes: str | None = None


class PayrollRunItemIn(_MgmtBase):
    staff_id: int = Field(..., ge=1)
    gross: float = 0
    deductions: float = 0
    net: float | None = None
    notes: str | None = None


class PayrollRunCreateBody(_MgmtBase):
    period_label: str = Field(..., min_length=1, max_length=64)
    run_date: Date | None = None
    status: str = "draft"
    items: list[PayrollRunItemIn] = Field(..., min_length=1)


# ---- Certificates / ID cards ----


class CertificateTemplateCreateBody(_MgmtBase):
    name: str = Field(..., min_length=1)
    template_type: str = "general"
    body_text: str | None = None


class CertificateTemplatePatchBody(_MgmtBase):
    name: str | None = Field(default=None, min_length=1)
    template_type: str | None = None
    body_text: str | None = None


class CertificateIssueBody(_MgmtBase):
    template_id: int = Field(..., ge=1)
    student_id: int = Field(..., ge=1)
    certificate_no: str | None = None
    data: dict[str, Any] | list[Any] | None = None


class IdCardSettingsPutBody(_MgmtBase):
    front_template: str | None = None
    back_template: str | None = None
    show_fields: dict[str, Any] | list[Any] | None = None
    show_fields_json: str | None = None


# ---- Diary / notifications / announcements / CMS ----


class DiaryCategoryCreateBody(_MgmtBase):
    name: str = Field(..., min_length=1)


class StudentDiaryCreateBody(_MgmtBase):
    student_id: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    category_id: int | None = Field(default=None, ge=1)
    body: str | None = None
    entry_date: Date | None = None


class NotificationCreateBody(_MgmtBase):
    title: str = Field(..., min_length=1)
    body: str | None = None
    status: int = 1


class AnnouncementCreateBody(_MgmtBase):
    title: str = Field(..., min_length=1)
    session_year_id: int = Field(..., ge=1)
    description: str | None = None
    body: str | None = Field(default=None, description="Alias for description")


class SliderCreateBody(_MgmtBase):
    title: str = Field(..., min_length=1)
    image_url: str | None = None
    link_url: str | None = None
    sort_order: int = 0
    status: int = 1


class SliderPatchBody(_MgmtBase):
    title: str | None = Field(default=None, min_length=1)
    image_url: str | None = None
    link_url: str | None = None
    sort_order: int | None = None
    status: int | None = None


class GalleryCreateBody(_MgmtBase):
    title: str = Field(..., min_length=1)
    image_url: str | None = None
    sort_order: int = 0
