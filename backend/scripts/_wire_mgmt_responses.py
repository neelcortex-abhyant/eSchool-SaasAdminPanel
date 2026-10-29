"""Attach json_response(...) to school_admin_mgmt routes lacking named responses."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app" / "api" / "v1" / "school_admin_mgmt.py"
text = path.read_text(encoding="utf-8")

IMPORT_MARK = "from app.schemas.v1.school_admin_erp_responses import ("
if "school_admin_mgmt_responses" not in text:
    # Prefer importing mgmt response helpers; keep erp DeletedOut/json_response usage
    insert = (
        "from app.schemas.v1 import school_admin_mgmt_responses as mgmt_out\n"
        "from app.schemas.v1.school_admin_erp_responses import ("
    )
    text = text.replace(IMPORT_MARK, insert, 1)

# function_name -> (status_code or None for 200, ModelName)
# status_code None means default 200; 201 for creates
MAP: dict[str, tuple[int | None, str]] = {
    # Question bank
    "list_question_bank": (200, "QuestionBankListOut"),
    "create_question_bank": (201, "QuestionBankOut"),
    "get_question_bank": (200, "QuestionBankOut"),
    "patch_question_bank": (200, "QuestionBankOut"),
    "delete_question_bank": (200, "DeletedOut"),
    "copy_from_bank": (201, "CopyFromBankOut"),
    # Admission / holidays
    "list_admission_inquiries": (200, "AdmissionInquiryListOut"),
    "create_admission_inquiry": (201, "AdmissionInquiryOut"),
    "patch_admission_inquiry": (200, "AdmissionInquiryOut"),
    "delete_admission_inquiry": (200, "DeletedOut"),
    "list_holidays": (200, "HolidayListOut"),
    "create_holiday": (201, "HolidayOut"),
    "patch_holiday": (200, "HolidayOut"),
    "delete_holiday": (200, "DeletedOut"),
    # Students extras
    "import_students": (201, "StudentsImportOut"),
    "promote_students": (200, "StudentsPromoteOut"),
    "transfer_student": (200, "StudentTransferOut"),
    "reset_student_password": (200, "StudentPasswordResetOut"),
    "list_electives": (200, "StudentElectiveListOut"),
    "assign_elective": (201, "StudentElectiveOut"),
    "remove_elective": (200, "DeletedOut"),
    # Semesters / streams / shifts / syllabi / online classes
    "list_semesters": (200, "SemesterListOut"),
    "create_semester": (201, "SemesterOut"),
    "patch_semester": (200, "SemesterOut"),
    "delete_semester": (200, "DeletedOut"),
    "list_streams": (200, "StreamListOut"),
    "create_stream": (201, "StreamOut"),
    "patch_stream": (200, "StreamOut"),
    "delete_stream": (200, "DeletedOut"),
    "list_shifts": (200, "ShiftListOut"),
    "create_shift": (201, "ShiftOut"),
    "patch_shift": (200, "ShiftOut"),
    "delete_shift": (200, "DeletedOut"),
    "list_syllabi": (200, "SyllabusListOut"),
    "create_syllabus": (201, "SyllabusOut"),
    "patch_syllabus": (200, "SyllabusOut"),
    "delete_syllabus": (200, "DeletedOut"),
    "list_online_classes": (200, "OnlineClassListOut"),
    "create_online_class": (201, "OnlineClassOut"),
    "patch_online_class": (200, "OnlineClassOut"),
    "delete_online_class": (200, "DeletedOut"),
    # Staff roles / import / attendance / tasks
    "list_staff_roles": (200, "StaffRolesListOut"),
    "get_staff_roles": (200, "StaffUserRolesOut"),
    "put_staff_roles": (200, "StaffUserRolesOut"),
    "import_staff": (201, "StaffImportOut"),
    "mark_staff_attendance": (201, "StaffAttendanceOut"),
    "staff_attendance_today": (200, "StaffAttendanceTodayOut"),
    "staff_attendance_register": (200, "StaffAttendanceRegisterOut"),
    "staff_attendance_reports": (200, "StaffAttendanceReportOut"),
    "get_staff_qr_settings": (200, "StaffQrSettingsOut"),
    "put_staff_qr_settings": (200, "StaffQrSettingsOut"),
    "list_staff_tasks": (200, "StaffTaskListOut"),
    "create_staff_task": (201, "StaffTaskOut"),
    "patch_staff_task": (200, "StaffTaskOut"),
    "delete_staff_task": (200, "DeletedOut"),
    # Expense / income / payroll
    "list_expense_categories": (200, "NamedCategoryListOut"),
    "create_expense_category": (201, "NamedCategoryOut"),
    "patch_expense_category": (200, "NamedCategoryOut"),
    "delete_expense_category": (200, "DeletedOut"),
    "list_income_categories": (200, "NamedCategoryListOut"),
    "create_income_category": (201, "NamedCategoryOut"),
    "delete_income_category": (200, "DeletedOut"),
    "incomes_dashboard": (200, "IncomesDashboardOut"),
    "list_incomes": (200, "IncomeListOut"),
    "create_income": (201, "IncomeOut"),
    "patch_income": (200, "IncomeOut"),
    "delete_income": (200, "DeletedOut"),
    "get_payroll_settings": (200, "PayrollSettingsOut"),
    "put_payroll_settings": (200, "PayrollSettingsOut"),
    "list_payroll_runs": (200, "PayrollRunListOut"),
    "create_payroll_run": (201, "PayrollRunOut"),
    # Certificates / id cards
    "list_certificate_templates": (200, "CertificateTemplateListOut"),
    "create_certificate_template": (201, "CertificateTemplateOut"),
    "patch_certificate_template": (200, "CertificateTemplateOut"),
    "delete_certificate_template": (200, "DeletedOut"),
    "issue_certificate": (201, "CertificateIssueOut"),
    "get_id_card_settings": (200, "IdCardSettingsOut"),
    "put_id_card_settings": (200, "IdCardSettingsOut"),
    "student_id_card": (200, "StudentIdCardOut"),
    "staff_id_card": (200, "StaffIdCardOut"),
    # Reports
    "reports_students": (200, "ReportStudentsOut"),
    "reports_teachers": (200, "ReportTeachersOut"),
    "reports_staff": (200, "ReportStaffOut"),
    "reports_exams": (200, "ReportExamsOut"),
    "reports_expenses": (200, "ReportAmountCountOut"),
    "reports_income": (200, "ReportAmountCountOut"),
    "reports_financial_summary": (200, "ReportFinancialSummaryOut"),
    # Diary / CMS
    "list_diary_categories": (200, "DiaryCategoryListOut"),
    "create_diary_category": (201, "DiaryCategoryOut"),
    "delete_diary_category": (200, "DeletedOut"),
    "list_student_diaries": (200, "StudentDiaryListOut"),
    "create_student_diary": (201, "StudentDiaryOut"),
    "delete_student_diary": (200, "DeletedOut"),
    "list_notifications": (200, "NotificationListOut"),
    "create_notification": (201, "NotificationOut"),
    "list_announcements": (200, "AnnouncementListOut"),
    "create_announcement": (201, "AnnouncementOut"),
    "list_sliders": (200, "SliderListOut"),
    "create_slider": (201, "SliderOut"),
    "patch_slider": (200, "SliderOut"),
    "delete_slider": (200, "DeletedOut"),
    "list_gallery": (200, "GalleryListOut"),
    "create_gallery_item": (201, "GalleryItemOut"),
    "delete_gallery_item": (200, "DeletedOut"),
    "subscription_plans": (200, "SubscriptionPlansOut"),
    "subscription_addons": (200, "SubscriptionAddonsOut"),
}


def add_responses(src: str, fn: str, code: int, model: str) -> str:
    # Find decorator block immediately above `def fn(`
    pattern = rf"((?:@[^\n]+\n)+)(def {fn}\()"
    m = re.search(pattern, src)
    if not m:
        raise SystemExit(f"function not found: {fn}")
    decorators = m.group(1)
    if "responses=" in decorators:
        return src  # already documented
    # Attach to the last @router... decorator line in the block
    lines = decorators.rstrip("\n").split("\n")
    last = lines[-1]
    resp = f"responses=mgmt_out.json_response(mgmt_out.{model}"
    if code != 200:
        resp += f", status_code={code}"
    resp += ")"
    if last.endswith(")"):
        # @router.get("/x") or @router.get("/x", status_code=...)
        if last.rstrip().endswith("()"):
            raise SystemExit(f"unexpected empty decorator for {fn}: {last}")
        if last.count("(") == last.count(")"):
            # insert before final )
            new_last = last[:-1] + f", {resp})"
        else:
            raise SystemExit(f"unbalanced decorator for {fn}: {last}")
    else:
        raise SystemExit(f"cannot parse decorator for {fn}: {last}")
    lines[-1] = new_last
    new_decorators = "\n".join(lines) + "\n"
    return src[: m.start(1)] + new_decorators + src[m.start(2) :]


for fn, (code, model) in MAP.items():
    text = add_responses(text, fn, code or 200, model)

path.write_text(text, encoding="utf-8")
print(f"Updated {path} with {len(MAP)} response mappings")
