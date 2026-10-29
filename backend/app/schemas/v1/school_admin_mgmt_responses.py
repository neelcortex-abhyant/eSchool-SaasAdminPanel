"""OpenAPI response models for Academic Management wave.

Derived from ``_row_dict`` / service return shapes. Documented via
``responses=json_response(...)`` without changing runtime serialization.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.v1.school_admin_erp_responses import DeletedOut, json_response

__all__ = [
    "DeletedOut",
    "json_response",
    "PageOut",
    "AdmissionInquiryOut",
    "AdmissionInquiryListOut",
    "HolidayOut",
    "HolidayListOut",
    "QuestionBankChoiceOut",
    "QuestionBankOut",
    "QuestionBankListOut",
    "CopyFromBankOut",
    "StudentElectiveOut",
    "StudentElectiveListOut",
    "StudentTransferOut",
    "StudentsPromoteOut",
    "StudentsImportOut",
    "StudentPasswordResetOut",
    "SemesterOut",
    "SemesterListOut",
    "StreamOut",
    "StreamListOut",
    "ShiftOut",
    "ShiftListOut",
    "SyllabusOut",
    "SyllabusListOut",
    "OnlineClassOut",
    "OnlineClassListOut",
    "StaffAttendanceOut",
    "StaffAttendanceTodayOut",
    "StaffAttendanceRegisterItemOut",
    "StaffAttendanceRegisterOut",
    "StaffAttendanceReportOut",
    "StaffQrSettingsOut",
    "StaffTaskOut",
    "StaffTaskListOut",
    "NamedCategoryOut",
    "NamedCategoryListOut",
    "IncomeOut",
    "IncomeListOut",
    "IncomesDashboardOut",
    "PayrollSettingsOut",
    "PayrollRunOut",
    "PayrollRunListOut",
    "SalaryStructureOut",
    "SalaryStructureListOut",
    "SalaryAssignmentOut",
    "SalaryAssignmentListOut",
    "PayrollPreviewOut",
    "PayrollProcessOut",
    "PayslipOut",
    "PayslipListOut",
    "PayrollSummaryOut",
    "CertificateTemplateOut",
    "CertificateTemplateListOut",
    "CertificateIssueOut",
    "CertificateIssueListOut",
    "CertificateVerifyOut",
    "IdCardSettingsOut",
    "StudentIdCardOut",
    "StaffIdCardOut",
    "DiaryCategoryOut",
    "DiaryCategoryListOut",
    "StudentDiaryOut",
    "StudentDiaryListOut",
    "NotificationOut",
    "NotificationListOut",
    "AnnouncementOut",
    "AnnouncementListOut",
    "SliderOut",
    "SliderListOut",
    "GalleryItemOut",
    "GalleryListOut",
    "StaffRoleOut",
    "StaffRolesListOut",
    "StaffUserRolesOut",
    "StaffImportOut",
    "StaffImportCreatedOut",
    "ReportStudentsOut",
    "ReportTeachersOut",
    "ReportStaffOut",
    "ReportExamsOut",
    "ReportAmountCountOut",
    "ReportFinancialSummaryOut",
    "SubscriptionPlanOut",
    "SubscriptionPlansOut",
    "SubscriptionAddonOut",
    "SubscriptionAddonsOut",
]


class _Out(BaseModel):
    model_config = ConfigDict(extra="ignore")


class PageOut(_Out):
    items: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


# ---- Admission / holidays / question bank ----


class AdmissionInquiryOut(_Out):
    id: int
    school_id: int
    student_name: str
    parent_name: str | None = None
    email: str | None = None
    mobile: str | None = None
    class_interested: str | None = None
    message: str | None = None
    status: str
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AdmissionInquiryListOut(_Out):
    items: list[AdmissionInquiryOut]
    total: int
    page: int
    page_size: int


class HolidayOut(_Out):
    id: int
    school_id: int
    title: str
    holiday_date: str
    end_date: str | None = None
    description: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class HolidayListOut(_Out):
    items: list[HolidayOut]
    total: int
    page: int
    page_size: int


class QuestionBankChoiceOut(_Out):
    id: int
    choice_text: str
    is_correct: int
    sort_order: int


class QuestionBankOut(_Out):
    id: int
    school_id: int
    subject_id: int | None = None
    question_text: str
    topic: str | None = None
    question_type: str
    marks: float
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    choices: list[QuestionBankChoiceOut] = Field(default_factory=list)


class QuestionBankListOut(_Out):
    items: list[QuestionBankOut]
    total: int
    page: int
    page_size: int


class CopyFromBankOut(_Out):
    assessment_id: int
    copied_question_ids: list[int]
    count: int


# ---- Students extras ----


class StudentElectiveOut(_Out):
    id: int
    school_id: int
    student_id: int
    subject_id: int
    session_year_id: int
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class StudentElectiveListOut(_Out):
    items: list[StudentElectiveOut]
    total: int


class StudentTransferOut(_Out):
    id: int
    school_id: int
    student_id: int
    from_class_section_id: int | None = None
    to_school_name: str | None = None
    reason: str | None = None
    transfer_date: str
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    enrollment_status: str | None = None


class StudentsPromoteOut(_Out):
    promoted: list[int]
    count: int


class StudentsImportOut(_Out):
    created: int


class StudentPasswordResetOut(_Out):
    student_id: int
    user_id: int
    reset: bool = True


# ---- Semesters / streams / shifts / syllabi / online classes ----


class SemesterOut(_Out):
    id: int
    school_id: int
    session_year_id: int
    name: str
    start_date: str | None = None
    end_date: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SemesterListOut(_Out):
    items: list[SemesterOut]
    total: int
    page: int
    page_size: int


class StreamOut(_Out):
    id: int
    school_id: int
    name: str
    description: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class StreamListOut(_Out):
    items: list[StreamOut]
    total: int
    page: int
    page_size: int


class ShiftOut(_Out):
    id: int
    school_id: int
    name: str
    start_time: str | None = None
    end_time: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ShiftListOut(_Out):
    items: list[ShiftOut]
    total: int
    page: int
    page_size: int


class SyllabusOut(_Out):
    id: int
    school_id: int
    title: str
    class_id: int | None = None
    subject_id: int | None = None
    session_year_id: int | None = None
    content: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SyllabusListOut(_Out):
    items: list[SyllabusOut]
    total: int
    page: int
    page_size: int


class OnlineClassOut(_Out):
    id: int
    school_id: int
    title: str
    class_section_id: int | None = None
    subject_id: int | None = None
    teacher_user_id: int | None = None
    meeting_url: str | None = None
    scheduled_at: str | None = None
    duration_minutes: int | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class OnlineClassListOut(_Out):
    items: list[OnlineClassOut]
    total: int
    page: int
    page_size: int


# ---- Staff attendance / QR / tasks ----


class StaffAttendanceOut(_Out):
    id: int
    school_id: int
    staff_id: int
    attendance_date: str
    status: str
    check_in: str | None = None
    check_out: str | None = None
    remark: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class StaffAttendanceTodayOut(_Out):
    date: str
    items: list[StaffAttendanceOut]
    total: int


class StaffAttendanceRegisterItemOut(_Out):
    staff_id: int
    attendance: StaffAttendanceOut | None = None


class StaffAttendanceRegisterOut(_Out):
    date: str
    items: list[StaffAttendanceRegisterItemOut]
    total: int


class StaffAttendanceReportOut(_Out):
    items: list[StaffAttendanceOut]
    total: int
    summary: dict[str, int]


class StaffQrSettingsOut(_Out):
    id: int | None = None
    school_id: int
    enabled: int = 0
    token: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class StaffTaskOut(_Out):
    id: int
    school_id: int
    title: str
    description: str | None = None
    assigned_to_staff_id: int | None = None
    due_date: str | None = None
    status: str
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class StaffTaskListOut(_Out):
    items: list[StaffTaskOut]
    total: int
    page: int
    page_size: int


# ---- Expense / income / payroll ----


class NamedCategoryOut(_Out):
    id: int
    school_id: int
    name: str
    description: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class NamedCategoryListOut(_Out):
    items: list[NamedCategoryOut]
    total: int
    page: int
    page_size: int


class IncomeOut(_Out):
    id: int
    school_id: int
    category_id: int | None = None
    title: str
    amount: float
    income_date: str
    session_year_id: int | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class IncomeListOut(_Out):
    items: list[IncomeOut]
    total: int
    page: int
    page_size: int


class IncomesDashboardOut(_Out):
    income_total: float
    expense_total: float
    net: float


class PayrollSettingsOut(_Out):
    id: int | None = None
    school_id: int
    pay_day: int | None = None
    currency: str = "INR"
    notes: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PayrollRunOut(_Out):
    id: int
    school_id: int
    period_label: str
    run_date: str
    status: str
    total_amount: float
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PayrollRunListOut(_Out):
    items: list[PayrollRunOut]
    total: int
    page: int
    page_size: int


class SalaryStructureLineOut(_Out):
    name: str
    amount: float = 0
    kind: str | None = None


class SalaryStructureOut(_Out):
    id: int
    name: str
    basic: float = 0
    allowances: list[SalaryStructureLineOut | dict[str, Any]] = Field(default_factory=list)
    deductions: list[SalaryStructureLineOut | dict[str, Any]] = Field(default_factory=list)
    gross: float = 0
    net: float = 0
    assigned: int = 0
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class SalaryStructureListOut(_Out):
    items: list[SalaryStructureOut]
    total: int
    page: int
    page_size: int


class SalaryAssignmentOut(_Out):
    id: int
    staff_id: int
    staff_name: str | None = None
    structure_id: int
    structure_name: str | None = None
    effective_from: str | None = None
    created_at: str | None = None


class SalaryAssignmentListOut(_Out):
    items: list[SalaryAssignmentOut]
    total: int
    page: int
    page_size: int


class PayrollPreviewLineOut(_Out):
    staff_id: int
    name: str | None = None
    department: str | None = None
    structure_name: str | None = None
    basic: float = 0
    allowances: float = 0
    deductions: float = 0
    attendance_adjustment: float = 0
    working_days: int | None = None
    paid_days: int | None = None
    gross: float | None = None
    net: float = 0
    eligible: bool = True
    problem: str | None = None


class PayrollPreviewOut(_Out):
    month: str
    items: list[PayrollPreviewLineOut | dict[str, Any]] = Field(default_factory=list)
    total_net: float = 0
    already_processed: bool = False


class PayrollProcessOut(_Out):
    processed: int = 0
    failed: int = 0
    run_id: int | None = None
    month: str | None = None
    total_net: float | None = None
    idempotent_replay: bool | None = None


class PayslipOut(_Out):
    id: int
    month: str | None = None
    staff_id: int
    name: str | None = None
    employee_code: str | None = None
    department: str | None = None
    designation: str | None = None
    basic: float = 0
    allowances: list[Any] = Field(default_factory=list)
    deductions: list[Any] = Field(default_factory=list)
    attendance_adjustment: float = 0
    working_days: int | None = None
    paid_days: int | None = None
    gross: float = 0
    net: float = 0
    status: str | None = None
    processed_at: str | None = None
    failure_reason: str | None = None
    payslip_ref: str | None = None
    run_id: int | None = None


class PayslipListOut(_Out):
    items: list[PayslipOut]
    total: int
    page: int
    page_size: int


class PayrollSummaryMonthOut(_Out):
    month: str
    processed: int = 0
    pending: int = 0
    failed: int = 0
    total_net: float = 0


class PayrollSummaryOut(_Out):
    items: list[PayrollSummaryMonthOut | dict[str, Any]] = Field(default_factory=list)


# ---- Certificates / ID cards ----


class CertificateTemplateOut(_Out):
    id: int
    school_id: int
    name: str
    template_type: str
    body_text: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class CertificateTemplateListOut(_Out):
    items: list[CertificateTemplateOut]
    total: int
    page: int
    page_size: int


class CertificateIssueOut(_Out):
    id: int
    school_id: int
    template_id: int
    student_id: int | None = None
    staff_id: int | None = None
    certificate_no: str
    issued_at: str | None = None
    data_json: str | None = None
    status: str | None = "issued"
    verification_token: str | None = None
    qr_verify_url: str | None = None
    verify_url: str | None = None
    revoked_at: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class CertificateIssueListOut(_Out):
    items: list[CertificateIssueOut]
    total: int
    page: int
    page_size: int


class CertificateVerifyOut(_Out):
    valid: bool
    status: str
    certificate_no: str | None = None
    issued_at: str | None = None
    revoked_at: str | None = None
    subject_type: str | None = None


class IdCardSettingsOut(_Out):
    id: int | None = None
    school_id: int
    front_template: str | None = None
    back_template: str | None = None
    show_fields_json: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class StudentIdCardOut(_Out):
    type: str
    student_id: int
    admission_no: str | None = None
    roll_number: int | None = None
    class_section_id: int | None = None
    session_year_id: int | None = None
    first_name: str = ""
    last_name: str = ""
    image: str | None = None
    settings: IdCardSettingsOut | dict[str, Any]
    qr_verify_url: str | None = None
    qr_code_url: str | None = None


class StaffIdCardOut(_Out):
    type: str
    staff_id: int
    employee_id: str | None = None
    department: str | None = None
    designation: str | None = None
    first_name: str = ""
    last_name: str = ""
    image: str | None = None
    settings: IdCardSettingsOut | dict[str, Any]
    qr_verify_url: str | None = None
    qr_code_url: str | None = None


# ---- Diary / notifications / CMS ----


class DiaryCategoryOut(_Out):
    id: int
    school_id: int
    name: str
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class DiaryCategoryListOut(_Out):
    items: list[DiaryCategoryOut]
    total: int
    page: int
    page_size: int


class StudentDiaryOut(_Out):
    id: int
    school_id: int
    category_id: int | None = None
    student_id: int
    title: str
    body: str | None = None
    entry_date: str
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class StudentDiaryListOut(_Out):
    items: list[StudentDiaryOut]
    total: int
    page: int
    page_size: int


class NotificationOut(_Out):
    id: int
    title: str
    body: str | None = None
    status: int
    school_id: int | None = None
    created_by: str | None = None
    audience: list[str] | list[Any] | None = None
    delivery: str | None = "queued"
    recipients: int | None = None
    delivered: int | None = None
    failed: int | None = None
    failure_reason: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class NotificationListOut(_Out):
    items: list[NotificationOut]
    total: int
    page: int
    page_size: int


class AnnouncementOut(_Out):
    id: int
    title: str
    description: str | None = None
    session_year_id: int
    school_id: int
    status: str | None = "published"
    audience: list[str] | list[Any] | None = None
    publish_at: str | None = None
    published_at: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AnnouncementListOut(_Out):
    items: list[AnnouncementOut]
    total: int
    page: int
    page_size: int


class SliderOut(_Out):
    id: int
    school_id: int
    title: str
    image_url: str | None = None
    link_url: str | None = None
    sort_order: int
    status: int
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SliderListOut(_Out):
    items: list[SliderOut]
    total: int
    page: int
    page_size: int


class GalleryItemOut(_Out):
    id: int
    school_id: int
    title: str
    image_url: str | None = None
    sort_order: int
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class GalleryListOut(_Out):
    items: list[GalleryItemOut]
    total: int
    page: int
    page_size: int


# ---- Staff roles / import ----


class StaffRoleOut(_Out):
    id: int
    name: str
    school_id: int | None = None


class StaffRolesListOut(_Out):
    items: list[StaffRoleOut]
    total: int


class StaffUserRolesOut(_Out):
    user_id: int
    roles: list[StaffRoleOut]


class StaffImportCreatedOut(_Out):
    row: int
    user_id: int
    staff_id: int
    email: str


class StaffImportOut(_Out):
    created: int
    items: list[StaffImportCreatedOut] = Field(default_factory=list)


# ---- Reports / subscription ----


class ReportStudentsOut(_Out):
    total: int
    by_enrollment_status: dict[str, int]


class ReportTeachersOut(_Out):
    total_staff: int


class ReportStaffOut(_Out):
    total: int
    by_employment_status: dict[str, int]


class ReportExamsOut(_Out):
    exams: int
    processed_results: int


class ReportAmountCountOut(_Out):
    total_amount: float
    count: int


class ReportFinancialSummaryOut(_Out):
    income_total: float
    expense_total: float
    fees_collected: float
    net: float


class SubscriptionPlanOut(_Out):
    id: int
    name: str
    description: str | None = None
    monthly_price: float | None = None
    yearly_price: float | None = None
    student_limit: int | None = None
    staff_limit: int | None = None
    status: int | None = None


class SubscriptionPlansOut(_Out):
    items: list[SubscriptionPlanOut]
    total: int


class SubscriptionAddonOut(_Out):
    id: int
    name: str | None = None
    description: str | None = None
    price: float | None = None
    status: int | None = None


class SubscriptionAddonsOut(_Out):
    items: list[SubscriptionAddonOut]
    total: int
