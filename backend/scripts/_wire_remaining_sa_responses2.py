"""Wire remaining school-admin JSON/binary response docs (pass 2)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SA = ROOT / "app" / "api" / "v1" / "school_admin.py"

WIRE = {
    ("GET", "/homework/{homework_id}/summary"): ("core_out", "HomeworkSummaryOut"),
    ("GET", "/offline-exam-marks/{mark_id}/audits"): ("core_out", "OfflineExamMarkAuditListOut"),
    ("GET", "/offline-exams/{exam_id}/results/summary"): ("core_out", "OfflineExamResultSummaryOut"),
    ("GET", "/online-assessment-attempts/{attempt_id}"): ("settings_out", "OnlineAssessmentAttemptOut"),
    ("GET", "/online-assessments/{assessment_id}/attempts"): ("settings_out", "OnlineAssessmentAttemptListOut"),
    ("GET", "/people"): ("core_out", "PeopleListOut"),
    ("GET", "/staff/departments"): ("core_out", "DepartmentListOut"),
    ("GET", "/teachers/departments"): ("core_out", "DepartmentListOut"),
    ("GET", "/teachers/{teacher_user_id}/availability"): ("core_out", "TeacherAvailabilityOut"),
    ("GET", "/teachers/{teacher_user_id}/timetable"): ("core_out", "WeeklyTimetableOut"),
    ("GET", "/teachers/{teacher_user_id}/timetable/daily"): ("core_out", "TeacherDailyTimetableOut"),
    ("GET", "/teachers/{teacher_user_id}/timetable/weekly"): ("core_out", "WeeklyTimetableOut"),
    ("GET", "/timetable/weekly"): ("core_out", "WeeklyTimetableOut"),
}

BINARY = {
    ("GET", "/students/{student_id}/photo"),
    ("GET", "/teachers/{teacher_id}/photo"),
    ("GET", "/staff/{staff_id}/photo"),
    ("GET", "/students/{student_id}/documents/{document_id}/download"),
    ("GET", "/teachers/{teacher_id}/documents/{document_id}/download"),
    ("GET", "/staff/{staff_id}/documents/{document_id}/download"),
    ("GET", "/study-materials/{material_id}/download"),
}


def inject_json(src: str, method: str, path: str, alias: str, model: str) -> tuple[str, bool]:
    meth = method.lower()
    pattern = re.compile(
        rf'(@router\.{meth}\(\s*"{re.escape(path)}"(?![^)]*responses=))([^)]*)\)',
        re.MULTILINE,
    )

    def repl(m: re.Match) -> str:
        head, rest = m.group(1), m.group(2).rstrip()
        frag = f"{alias}.json_response({alias}.{model})"
        if rest.strip():
            return f"{head}{rest}, responses={frag})"
        return f"{head}, responses={frag})"

    new, n = pattern.subn(repl, src, count=1)
    return new, n == 1


def inject_binary(src: str, method: str, path: str) -> tuple[str, bool]:
    meth = method.lower()
    pattern = re.compile(
        rf'(@router\.{meth}\(\s*"{re.escape(path)}"(?![^)]*responses=))([^)]*)\)',
        re.MULTILINE,
    )

    def repl(m: re.Match) -> str:
        head, rest = m.group(1), m.group(2).rstrip()
        frag = "core_out.binary_file_response(), response_class=Response"
        if rest.strip():
            return f"{head}{rest}, responses={frag})"
        return f"{head}, responses={frag})"

    new, n = pattern.subn(repl, src, count=1)
    return new, n == 1


def main() -> None:
    src = SA.read_text(encoding="utf-8")
    for (method, route), (alias, model) in WIRE.items():
        src2, ok = inject_json(src, method, route, alias, model)
        print(("OK" if ok else "MISS"), method, route, "->", f"{alias}.{model}")
        if ok:
            src = src2
    for method, route in BINARY:
        src2, ok = inject_binary(src, method, route)
        print(("OK" if ok else "MISS"), method, route, "-> binary")
        if ok:
            src = src2
    SA.write_text(src, encoding="utf-8")


if __name__ == "__main__":
    main()
