"""Wire named response schemas onto core school-admin + academics write routes."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def add_responses(src: str, fn: str, code: int, model_expr: str) -> str:
    pattern = rf"((?:@[^\n]+\n)+)(def {fn}\()"
    m = re.search(pattern, src)
    if not m:
        raise SystemExit(f"function not found: {fn}")
    decorators = m.group(1)
    if "responses=" in decorators:
        return src
    lines = decorators.rstrip("\n").split("\n")
    last = lines[-1]
    resp = f"responses={model_expr}"
    if not last.endswith(")"):
        raise SystemExit(f"cannot parse decorator for {fn}: {last}")
    new_last = last[:-1] + f", {resp})"
    lines[-1] = new_last
    new_decorators = "\n".join(lines) + "\n"
    return src[: m.start(1)] + new_decorators + src[m.start(2) :]


# ---- school_admin.py ----
admin = ROOT / "app" / "api" / "v1" / "school_admin.py"
text = admin.read_text(encoding="utf-8")
if "school_admin_core_responses" not in text:
    text = text.replace(
        "from app.services.v1 import school_timetable as timetable_svc\n",
        "from app.schemas.v1 import school_admin_core_responses as core_out\n"
        "from app.services.v1 import school_timetable as timetable_svc\n",
        1,
    )

ADMIN_MAP = {
    "create_class": (201, "core_out.json_response(core_out.ClassOut, status_code=201)"),
    "update_class": (200, "core_out.json_response(core_out.ClassOut)"),
    "create_section": (201, "core_out.json_response(core_out.SectionOut, status_code=201)"),
    "update_section": (200, "core_out.json_response(core_out.SectionOut)"),
    "create_subject": (201, "core_out.json_response(core_out.SubjectOut, status_code=201)"),
    "update_subject": (200, "core_out.json_response(core_out.SubjectOut)"),
    "create_people_student": (201, "core_out.json_response(core_out.StudentOut, status_code=201)"),
    "update_people_student": (200, "core_out.json_response(core_out.StudentOut)"),
    "update_people_student_status": (200, "core_out.json_response(core_out.StatusOut)"),
    "create_people_parent": (201, "core_out.json_response(core_out.ParentOut, status_code=201)"),
    "update_people_parent": (200, "core_out.json_response(core_out.ParentOut)"),
    "update_people_parent_status": (200, "core_out.json_response(core_out.StatusOut)"),
    "create_teacher": (201, "core_out.json_response(core_out.TeacherOut, status_code=201)"),
    "update_teacher": (200, "core_out.json_response(core_out.TeacherOut)"),
    "update_teacher_status": (200, "core_out.json_response(core_out.StatusOut)"),
    "create_staff": (201, "core_out.json_response(core_out.StaffOut, status_code=201)"),
    "update_staff": (200, "core_out.json_response(core_out.StaffOut)"),
    "update_staff_status": (200, "core_out.json_response(core_out.StatusOut)"),
    "create_timetable_entry": (201, "core_out.json_response(core_out.TimetableEntryOut, status_code=201)"),
    "update_timetable_entry": (200, "core_out.json_response(core_out.TimetableEntryOut)"),
    "delete_timetable_entry": (200, "core_out.json_response(core_out.DeletedOut)"),
    "create_teacher_assignment": (
        201,
        "core_out.json_response(core_out.TeacherAssignmentOut, status_code=201)",
    ),
    "update_teacher_assignment": (200, "core_out.json_response(core_out.TeacherAssignmentOut)"),
    "create_homework": (201, "core_out.json_response(core_out.HomeworkOut, status_code=201)"),
    "update_homework": (200, "core_out.json_response(core_out.HomeworkOut)"),
    "evaluate_homework_submission": (200, "core_out.json_response(core_out.HomeworkSubmissionOut)"),
}

for fn, (_code, expr) in ADMIN_MAP.items():
    text = add_responses(text, fn, _code, expr)

admin.write_text(text, encoding="utf-8")
print(f"school_admin.py wired {len(ADMIN_MAP)}")

# ---- academics ----
acad = ROOT / "app" / "api" / "v1" / "school_admin_academics.py"
atext = acad.read_text(encoding="utf-8")
if "school_admin_core_responses" not in atext:
    atext = atext.replace(
        "from app.services.v1 import rbac\n",
        "from app.schemas.v1 import school_admin_core_responses as core_out\n"
        "from app.services.v1 import rbac\n",
        1,
    )

ACAD_MAP = {
    "activate_session": (200, "core_out.json_response(core_out.SessionYearOut)"),
    "create": (201, "core_out.json_response(core_out.AcademicResourceOut, status_code=201)"),
    "update": (200, "core_out.json_response(core_out.AcademicResourceOut)"),
}

for fn, (_code, expr) in ACAD_MAP.items():
    atext = add_responses(atext, fn, _code, expr)

acad.write_text(atext, encoding="utf-8")
print(f"school_admin_academics.py wired {len(ACAD_MAP)}")
