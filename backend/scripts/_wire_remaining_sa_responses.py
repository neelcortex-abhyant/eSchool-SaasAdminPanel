"""Wire remaining school-admin GET/DELETE OpenAPI response models (one-shot)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# path_suffix -> (module_alias, ModelName)  — module_alias is core_out or settings_out
WIRE: dict[tuple[str, str], tuple[str, str]] = {
    # structure
    ("GET", "/classes"): ("core_out", "ClassListOut"),
    ("GET", "/classes/{class_id}"): ("core_out", "ClassOut"),
    ("GET", "/sections"): ("core_out", "SectionListOut"),
    ("GET", "/sections/{section_id}"): ("core_out", "SectionOut"),
    ("GET", "/subjects"): ("core_out", "SubjectListOut"),
    ("GET", "/subjects/{subject_id}"): ("core_out", "SubjectOut"),
    ("GET", "/subjects/{subject_id}/classes"): ("core_out", "SubjectClassesListOut"),
    ("GET", "/sessions"): ("core_out", "SessionYearListOut"),
    # people
    ("GET", "/students"): ("core_out", "StudentListOut"),
    ("GET", "/students/{student_id}"): ("core_out", "StudentOut"),
    ("DELETE", "/students/{student_id}/guardians/{parent_id}"): ("core_out", "StudentOut"),
    ("GET", "/students/{student_id}/documents"): ("core_out", "PersonDocumentListOut"),
    ("GET", "/students/{student_id}/documents/{document_id}"): ("core_out", "PersonDocumentOut"),
    ("DELETE", "/students/{student_id}/documents/{document_id}"): ("core_out", "SoftDeletedOut"),
    ("GET", "/parents"): ("core_out", "ParentListOut"),
    ("GET", "/parents/{parent_id}"): ("core_out", "ParentOut"),
    ("GET", "/teachers"): ("core_out", "TeacherListOut"),
    ("GET", "/teachers/{teacher_id}"): ("core_out", "TeacherOut"),
    ("GET", "/teachers/{teacher_id}/documents"): ("core_out", "PersonDocumentListOut"),
    ("GET", "/teachers/{teacher_id}/documents/{document_id}"): ("core_out", "PersonDocumentOut"),
    ("DELETE", "/teachers/{teacher_id}/documents/{document_id}"): ("core_out", "SoftDeletedOut"),
    ("GET", "/staff"): ("core_out", "StaffListOut"),
    ("GET", "/staff/{staff_id}"): ("core_out", "StaffOut"),
    ("GET", "/staff/{staff_id}/documents"): ("core_out", "PersonDocumentListOut"),
    ("GET", "/staff/{staff_id}/documents/{document_id}"): ("core_out", "PersonDocumentOut"),
    ("DELETE", "/staff/{staff_id}/documents/{document_id}"): ("core_out", "SoftDeletedOut"),
    # timetable / assignments
    ("GET", "/timetable-entries"): ("core_out", "TimetableEntryListOut"),
    ("GET", "/timetable-entries/{entry_id}"): ("core_out", "TimetableEntryOut"),
    ("GET", "/teacher-assignments"): ("core_out", "TeacherAssignmentListOut"),
    ("GET", "/teacher-assignments/{assignment_id}"): ("core_out", "TeacherAssignmentOut"),
    ("DELETE", "/teacher-assignments/{assignment_id}"): ("core_out", "SoftDeletedOut"),
    # homework
    ("GET", "/homework"): ("core_out", "HomeworkListOut"),
    ("GET", "/homework/{homework_id}"): ("core_out", "HomeworkOut"),
    ("DELETE", "/homework/{homework_id}"): ("core_out", "DeletedOut"),
    ("GET", "/homework/{homework_id}/submissions"): ("core_out", "HomeworkSubmissionListOut"),
    ("GET", "/homework-submissions/{submission_id}"): ("core_out", "HomeworkSubmissionOut"),
    # study materials / OA / offline
    ("GET", "/study-materials"): ("settings_out", "StudyMaterialListOut"),
    ("GET", "/study-materials/{material_id}"): ("settings_out", "StudyMaterialOut"),
    ("DELETE", "/study-materials/{material_id}"): ("core_out", "DeletedOut"),
    ("GET", "/online-assessments"): ("settings_out", "OnlineAssessmentListOut"),
    ("GET", "/online-assessments/{assessment_id}"): ("settings_out", "OnlineAssessmentOut"),
    ("DELETE", "/online-assessments/{assessment_id}"): ("core_out", "DeletedOut"),
    ("DELETE", "/online-assessment-questions/{question_id}"): ("core_out", "DeletedOut"),
    ("GET", "/offline-exams"): ("core_out", "OfflineExamListOut"),
    ("GET", "/offline-exams/{exam_id}"): ("core_out", "OfflineExamOut"),
    ("DELETE", "/offline-exams/{exam_id}"): ("core_out", "DeletedOut"),
    ("GET", "/offline-exam-schedules"): ("core_out", "OfflineExamScheduleListOut"),
    ("GET", "/offline-exam-schedules/{schedule_id}"): ("core_out", "OfflineExamScheduleOut"),
    ("DELETE", "/offline-exam-schedules/{schedule_id}"): ("core_out", "DeletedOut"),
    ("GET", "/offline-exam-marks"): ("core_out", "OfflineExamMarkListOut"),
    ("GET", "/offline-exams/{exam_id}/results"): ("core_out", "OfflineExamResultListOut"),
}

SETTINGS_WIRE: dict[tuple[str, str], tuple[str, str]] = {
    ("GET", "/content/{slug}"): ("settings_out", "ContentPageOut"),
    ("GET", "/web-content"): ("settings_out", "ContentPageOut"),
    ("GET", "/faqs"): ("settings_out", "FaqListOut"),
    ("DELETE", "/faqs/{faq_id}"): ("settings_out", "OkIdOut"),
    ("GET", "/leave-settings"): ("settings_out", "LeaveSettingsOut"),
    ("GET", "/online-exam-terms"): ("settings_out", "OnlineExamTermsOut"),
    ("GET", "/email-templates"): ("settings_out", "EmailTemplateListOut"),
    ("GET", "/email-templates/{template_id}"): ("settings_out", "EmailTemplateOut"),
    ("DELETE", "/email-templates/{template_id}"): ("settings_out", "OkIdOut"),
    ("GET", "/whatsapp-settings"): ("settings_out", "IntegrationSettingsOut"),
    ("GET", "/payment-gateway-settings"): ("settings_out", "IntegrationSettingsOut"),
    ("GET", "/third-party-integrations"): ("settings_out", "IntegrationSettingsListOut"),
    ("GET", "/user-form-fields"): ("settings_out", "UserFormFieldListOut"),
    ("DELETE", "/user-form-fields/{field_id}"): ("settings_out", "OkIdOut"),
    ("GET", "/contact-inquiries"): ("settings_out", "ContactInquiryListOut"),
    ("GET", "/contact-inquiries/{inquiry_id}"): ("settings_out", "ContactInquiryOut"),
    ("GET", "/support-tickets"): ("settings_out", "SupportTicketListOut"),
    ("GET", "/support-tickets/{ticket_id}"): ("settings_out", "SupportTicketOut"),
}


def _inject(src: str, method: str, path: str, alias: str, model: str) -> tuple[str, bool]:
    """Insert responses= into @router.<method>(\"path\"...) if missing."""
    meth = method.lower()
    # Match decorator that starts with @router.get("/path" or @router.delete("/path"
    # and may already have other kwargs but not responses=
    pattern = re.compile(
        rf'(@router\.{meth}\(\s*"{re.escape(path)}"(?![^)]*responses=))([^)]*)\)',
        re.MULTILINE,
    )

    def repl(m: re.Match) -> str:
        head, rest = m.group(1), m.group(2)
        rest = rest.rstrip()
        frag = f"{alias}.json_response({alias}.{model})"
        if rest.strip():
            return f"{head}{rest}, responses={frag})"
        return f"{head}, responses={frag})"

    new, n = pattern.subn(repl, src, count=1)
    return new, n == 1


def patch_file(path: Path, mapping: dict[tuple[str, str], tuple[str, str]]) -> list[str]:
    src = path.read_text(encoding="utf-8")
    done: list[str] = []
    for (method, route), (alias, model) in mapping.items():
        src2, ok = _inject(src, method, route, alias, model)
        if ok:
            src = src2
            done.append(f"{method} {route} -> {alias}.{model}")
        else:
            # already wired or pattern miss
            if f'"{route}"' in src and "responses=" in src:
                # check if this specific route already has responses nearby
                done.append(f"SKIP {method} {route} (no change)")
            else:
                done.append(f"MISS {method} {route}")
    path.write_text(src, encoding="utf-8")
    return done


def main() -> None:
    sa = ROOT / "app" / "api" / "v1" / "school_admin.py"
    settings = ROOT / "app" / "api" / "v1" / "school_admin_settings.py"
    print("=== school_admin.py ===")
    for line in patch_file(sa, WIRE):
        print(line)
    print("=== school_admin_settings.py ===")
    for line in patch_file(settings, SETTINGS_WIRE):
        print(line)


if __name__ == "__main__":
    main()
