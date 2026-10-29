"""One-shot: replace generic Body params in school_admin_mgmt routes with typed schemas."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app" / "api" / "v1" / "school_admin_mgmt.py"
text = path.read_text(encoding="utf-8")

# Insert import after existing erp schemas import block
old_import = "from app.schemas.v1 import school_admin_erp as erp_schemas"
new_import = (
    "from app.schemas.v1 import school_admin_erp as erp_schemas\n"
    "from app.schemas.v1 import school_admin_mgmt as mgmt_schemas"
)
if "school_admin_mgmt as mgmt_schemas" not in text:
    text = text.replace(old_import, new_import, 1)

# Replace Body class + helpers
old_helpers = '''class Body(BaseModel):
    model_config = ConfigDict(extra="allow")


def _school_id(auth: AuthContext) -> int:
    return int(auth.user.school_id)  # type: ignore[arg-type]


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


def _body(body: Body) -> dict[str, Any]:
    return mgmt.sanitize_body(body.model_dump(exclude_unset=True))


def _erp_body(body: BaseModel) -> dict[str, Any]:
    return mgmt.sanitize_body(erp_schemas.dump_erp_body(body))
'''

new_helpers = '''def _school_id(auth: AuthContext) -> int:
    return int(auth.user.school_id)  # type: ignore[arg-type]


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


def _mgmt_body(body: BaseModel) -> dict[str, Any]:
    return mgmt.sanitize_body(mgmt_schemas.dump_mgmt_body(body))


def _erp_body(body: BaseModel) -> dict[str, Any]:
    return mgmt.sanitize_body(erp_schemas.dump_erp_body(body))
'''

if "class Body(BaseModel):" in text:
    text = text.replace(old_helpers, new_helpers, 1)

# Map: function def name -> schema class name
FN_SCHEMA = {
    "create_question_bank": "mgmt_schemas.QuestionBankCreateBody",
    "patch_question_bank": "mgmt_schemas.QuestionBankPatchBody",
    "copy_from_bank": "mgmt_schemas.CopyFromBankBody",
    "create_admission_inquiry": "mgmt_schemas.AdmissionInquiryCreateBody",
    "patch_admission_inquiry": "mgmt_schemas.AdmissionInquiryPatchBody",
    "create_holiday": "mgmt_schemas.HolidayCreateBody",
    "patch_holiday": "mgmt_schemas.HolidayPatchBody",
    "import_students": "mgmt_schemas.StudentsImportBody",
    "promote_students": "mgmt_schemas.StudentsPromoteBody",
    "transfer_student": "mgmt_schemas.StudentTransferBody",
    "reset_student_password": "mgmt_schemas.StudentResetPasswordBody",
    "assign_elective": "mgmt_schemas.StudentElectiveCreateBody",
    "create_semester": "mgmt_schemas.SemesterCreateBody",
    "patch_semester": "mgmt_schemas.SemesterPatchBody",
    "create_stream": "mgmt_schemas.StreamCreateBody",
    "patch_stream": "mgmt_schemas.StreamPatchBody",
    "create_shift": "mgmt_schemas.ShiftCreateBody",
    "patch_shift": "mgmt_schemas.ShiftPatchBody",
    "create_syllabus": "mgmt_schemas.SyllabusCreateBody",
    "patch_syllabus": "mgmt_schemas.SyllabusPatchBody",
    "create_online_class": "mgmt_schemas.OnlineClassCreateBody",
    "patch_online_class": "mgmt_schemas.OnlineClassPatchBody",
    "put_staff_roles": "mgmt_schemas.StaffRolesPutBody",
    "import_staff": "mgmt_schemas.StaffImportBody",
    "mark_staff_attendance": "mgmt_schemas.StaffAttendanceMarkBody",
    "put_staff_qr_settings": "mgmt_schemas.StaffQrSettingsPutBody",
    "create_staff_task": "mgmt_schemas.StaffTaskCreateBody",
    "patch_staff_task": "mgmt_schemas.StaffTaskPatchBody",
    "create_expense_category": "mgmt_schemas.NamedCategoryCreateBody",
    "patch_expense_category": "mgmt_schemas.NamedCategoryPatchBody",
    "create_income_category": "mgmt_schemas.NamedCategoryCreateBody",
    "create_income": "mgmt_schemas.IncomeCreateBody",
    "patch_income": "mgmt_schemas.IncomePatchBody",
    "put_payroll_settings": "mgmt_schemas.PayrollSettingsPutBody",
    "create_payroll_run": "mgmt_schemas.PayrollRunCreateBody",
    "create_certificate_template": "mgmt_schemas.CertificateTemplateCreateBody",
    "patch_certificate_template": "mgmt_schemas.CertificateTemplatePatchBody",
    "issue_certificate": "mgmt_schemas.CertificateIssueBody",
    "put_id_card_settings": "mgmt_schemas.IdCardSettingsPutBody",
    "create_diary_category": "mgmt_schemas.DiaryCategoryCreateBody",
    "create_student_diary": "mgmt_schemas.StudentDiaryCreateBody",
    "create_notification": "mgmt_schemas.NotificationCreateBody",
    "create_announcement": "mgmt_schemas.AnnouncementCreateBody",
    "create_slider": "mgmt_schemas.SliderCreateBody",
    "patch_slider": "mgmt_schemas.SliderPatchBody",
    "create_gallery_item": "mgmt_schemas.GalleryCreateBody",
}

# Replace `def name(... body: Body` with typed schema
for fn, schema in FN_SCHEMA.items():
    pattern = rf"(def {fn}\([\s\S]*?\n\s+)body: Body,"
    repl = rf"\1body: {schema},"
    new_text, n = re.subn(pattern, repl, text, count=1)
    if n != 1:
        raise SystemExit(f"Failed to wire {fn}: matches={n}")
    text = new_text

# Replace _body(body) with _mgmt_body(body) globally in this file
text = text.replace("_body(body)", "_mgmt_body(body)")

# Special-case import_students / import_staff / copy_from_bank / put_staff_roles handlers
text = text.replace(
    '''def import_students(
    body: mgmt_schemas.StudentsImportBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    data = _mgmt_body(body)
    rows = data.get("rows") or data.get("students") or data.get("items") or []
    return _run(lambda: mgmt.bulk_import_students(db, _school_id(auth), rows))
''',
    '''def import_students(
    body: mgmt_schemas.StudentsImportBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    rows = body.row_list()
    return _run(lambda: mgmt.bulk_import_students(db, _school_id(auth), rows))
''',
)

text = text.replace(
    '''def copy_from_bank(
    assessment_id: int,
    body: mgmt_schemas.CopyFromBankBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    data = _mgmt_body(body)
    ids = data.get("question_ids") or []
    return _run(lambda: mgmt.copy_questions_to_assessment(db, _school_id(auth), assessment_id, ids))
''',
    '''def copy_from_bank(
    assessment_id: int,
    body: mgmt_schemas.CopyFromBankBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    ids = list(body.question_ids)
    return _run(lambda: mgmt.copy_questions_to_assessment(db, _school_id(auth), assessment_id, ids))
''',
)

text = text.replace(
    '''def put_staff_roles(
    user_id: int,
    body: mgmt_schemas.StaffRolesPutBody,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    data = _mgmt_body(body)
    roles = data.get("roles") or []
    if not isinstance(roles, list):
        raise HTTPException(status_code=422, detail="roles must be a list of role names")
    return _run(lambda: mgmt.set_staff_user_roles(db, _school_id(auth), user_id, roles))
''',
    '''def put_staff_roles(
    user_id: int,
    body: mgmt_schemas.StaffRolesPutBody,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    roles = list(body.roles)
    return _run(lambda: mgmt.set_staff_user_roles(db, _school_id(auth), user_id, roles))
''',
)

text = text.replace(
    '''def import_staff(
    body: mgmt_schemas.StaffImportBody,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    data = _mgmt_body(body)
    rows = data.get("rows") or data.get("items") or []
    if not isinstance(rows, list):
        raise HTTPException(status_code=422, detail="rows must be a list")
    return _run(lambda: mgmt.bulk_import_staff(db, _school_id(auth), rows))
''',
    '''def import_staff(
    body: mgmt_schemas.StaffImportBody,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    rows = body.row_list()
    return _run(lambda: mgmt.bulk_import_staff(db, _school_id(auth), rows))
''',
)

# Remove unused ConfigDict import if Body gone — keep ConfigDict only if still used
if "ConfigDict" in text and "ConfigDict(" not in text:
    text = text.replace("from pydantic import BaseModel, ConfigDict\n", "from pydantic import BaseModel\n")

if "body: Body" in text:
    raise SystemExit("Still have body: Body leftovers:\n" + "\n".join(
        line for line in text.splitlines() if "body: Body" in line
    ))

path.write_text(text, encoding="utf-8")
print(f"Updated {path}")
print("remaining _body(", text.count("_body("))
print("mgmt_body calls", text.count("_mgmt_body("))
