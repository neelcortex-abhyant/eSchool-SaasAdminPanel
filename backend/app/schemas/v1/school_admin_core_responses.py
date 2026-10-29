"""Response models for school-admin people / structure / timetable / homework writes.

Fields mirror service serializers (``_student_item``, ``_entry_item``, ``_homework_item``, …).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel

from app.schemas.v1.school_admin_erp_responses import DeletedOut, json_response

__all__ = [
    "DeletedOut",
    "json_response",
    "StudentOut",
    "ClassOut",
    "SectionOut",
    "SubjectOut",
    "SessionYearOut",
    "TeacherOut",
    "StaffOut",
    "ParentOut",
    "TimetableEntryOut",
    "TeacherAssignmentOut",
    "HomeworkAttachmentOut",
    "HomeworkOut",
    "HomeworkSubmissionOut",
    "AcademicResourceOut",
    "PersonDocumentOut",
    "PhotoUploadOut",
    "SubjectClassLinkOut",
    "SubjectClassesListOut",
    "OfflineExamOut",
    "OfflineExamScheduleOut",
    "OfflineExamMarkOut",
    "OfflineExamMarksBulkOut",
    "OfflineExamProcessResultsOut",
    "OfflineExamResultOut",
    "SoftDeletedOut",
    "ClassListOut",
    "SectionListOut",
    "SubjectListOut",
    "SessionYearListOut",
    "StudentListOut",
    "TeacherListOut",
    "StaffListOut",
    "ParentListOut",
    "TimetableEntryListOut",
    "TeacherAssignmentListOut",
    "HomeworkListOut",
    "HomeworkSubmissionListOut",
    "PersonDocumentListOut",
    "OfflineExamListOut",
    "OfflineExamScheduleListOut",
    "OfflineExamMarkListOut",
    "OfflineExamResultListOut",
]


class _Out(BaseModel):
    model_config = ConfigDict(extra="ignore")


class StudentOut(_Out):
    id: int
    user_id: int | None = None
    first_name: str = ""
    last_name: str = ""
    name: str | None = None
    email: str | None = None
    mobile: str | None = None
    admission_no: str | None = None
    roll_number: int | None = None
    class_section_id: int | None = None
    session_year_id: int | None = None
    session_name: str | None = None
    class_id: int | None = None
    class_name: str | None = None
    section_name: str | None = None
    guardian_id: int | None = None
    guardian_name: str | None = None
    guardian_mobile: str | None = None
    admission_date: str | None = None
    enrollment_status: str | None = None
    status: int = 0
    dob: str | None = None
    gender: str | None = None
    current_address: str | None = None
    permanent_address: str | None = None
    image: str | None = None
    photo_url: str | None = None
    guardians: list[Any] = Field(default_factory=list)
    documents: list[Any] = Field(default_factory=list)


class ClassOut(_Out):
    id: int
    name: str
    medium_id: int
    include_semesters: int = 0


class SectionOut(_Out):
    id: int
    name: str
    class_id: int | None = None
    class_section_id: int | None = None


class SubjectOut(_Out):
    id: int
    name: str
    code: str | None = None
    type: str | None = None
    medium_id: int | None = None


class SessionYearOut(_Out):
    id: int
    name: str
    default: int = 0
    start_date: str
    end_date: str


class TeacherOut(_Out):
    id: int
    staff_id: int
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    mobile: str | None = None
    gender: str | None = None
    dob: str | None = None
    current_address: str | None = None
    permanent_address: str | None = None
    country_code: str | None = None
    image: str | None = None
    photo_url: str | None = None
    status: int | None = None
    role: str | None = None
    qualification: str | None = None
    salary: float | None = None
    employee_id: str | None = None
    employee_code: str | None = None
    joining_date: str | None = None
    employment_status: str | None = None
    employment_type: str | None = None
    department: str | None = None
    designation: str | None = None
    assignment_count: int | None = None


class StaffOut(TeacherOut):
    """Non-teaching staff payload uses the same public fields as teachers (role=Staff)."""


class ParentOut(_Out):
    id: int
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    mobile: str | None = None
    status: int | None = None
    current_address: str | None = None
    occupation: str | None = None
    children: list[Any] = Field(default_factory=list)


class TimetableEntryOut(_Out):
    id: int
    entry_id: int | None = None
    session_year_id: int
    class_section_id: int
    class_id: int | None = None
    section_id: int | None = None
    class_name: str | None = None
    section_name: str | None = None
    subject_id: int
    subject_name: str | None = None
    teacher_user_id: int
    teacher_name: str | None = None
    staff_id: int | None = None
    day: str
    start_time: str
    end_time: str
    note: str | None = None
    room: str | None = None


class TeacherAssignmentOut(_Out):
    id: int
    staff_id: int | None = None
    teacher_user_id: int | None = None
    teacher_id: int | None = None
    subject_id: int | None = None
    class_section_id: int | None = None
    session_year_id: int | None = None
    name: str | None = None


class HomeworkAttachmentOut(_Out):
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None


class HomeworkOut(_Out):
    id: int
    session_year_id: int
    class_section_id: int
    subject_id: int
    subject_name: str | None = None
    teacher_user_id: int
    teacher_name: str | None = None
    title: str
    instructions: str | None = None
    assigned_date: str | None = None
    deadline_at: str | None = None
    max_marks: float | None = None
    allow_late: bool = True
    attachments: list[HomeworkAttachmentOut | dict[str, Any]] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class HomeworkSubmissionOut(_Out):
    id: int
    homework_id: int
    student_id: int
    student_name: str | None = None
    admission_no: str | None = None
    text_response: str | None = None
    status: str | None = None
    is_late: int | None = None
    marks: float | None = None
    grade: str | None = None
    feedback: str | None = None
    submitted_at: str | None = None
    evaluated_at: str | None = None


class AcademicResourceOut(_Out):
    """Union of fields returned by polymorphic ``/academics/{resource}`` writes.

    Only fields actually emitted by handlers; all optional except ``id``.
    """

    id: int
    name: str | None = None
    title: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    admission_no: str | None = None
    user_id: int | None = None
    student_id: int | None = None
    reason: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    status: int | None = None
    session_year_id: int | None = None
    medium_id: int | None = None
    class_id: int | None = None
    section_id: int | None = None
    subject_id: int | None = None
    code: str | None = None
    type: str | None = None
    include_semesters: int | None = None
    default: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    amount: float | None = None
    date: str | None = None
    due_date: str | None = None
    due_charges: float | None = None
    description: str | None = None
    deleted: bool | None = None


class PersonDocumentOut(_Out):
    """Public person document item (``document_public_item``)."""

    id: int
    title: str
    file_name: str | None = None
    content_type: str | None = None
    size: int | None = None
    url: str | None = None
    uploaded_at: str | None = None
    category: str | None = None
    size_bytes: int | None = None
    original_filename: str | None = None
    created_at: str | None = None


class PhotoUploadOut(_Out):
    """Contract-shaped photo upload response from people photo routes."""

    photo_url: str | None = None


class SubjectClassLinkOut(_Out):
    class_id: int
    class_name: str | None = None
    medium_id: int | None = None
    class_subject_id: int


class SubjectClassesListOut(_Out):
    items: list[SubjectClassLinkOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class OfflineExamOut(_Out):
    id: int
    name: str
    description: str | None = None
    class_id: int | None = None
    class_section_id: int | None = None
    session_year_id: int | None = None
    exam_type: str | None = None
    exam_date: str | None = None
    publish: bool = False
    results_processed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class OfflineExamScheduleOut(_Out):
    id: int
    exam_id: int
    session_year_id: int | None = None
    class_section_id: int | None = None
    subject_id: int
    subject_name: str | None = None
    teacher_user_id: int | None = None
    exam_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    max_marks: float | None = None
    passing_marks: float | None = None


class OfflineExamMarkOut(_Out):
    id: int
    exam_id: int
    schedule_id: int
    student_id: int
    student_name: str | None = None
    admission_no: str | None = None
    marks_obtained: float | None = None
    status: str | None = None
    evaluated_by_v1_user_id: str | None = None
    updated_at: str | None = None


class OfflineExamMarksBulkOut(_Out):
    created: int
    updated: int
    total: int


class OfflineExamProcessResultsOut(_Out):
    exam_id: int
    processed_students: int
    pending_students: int
    enrolled_students: int
    processed_at: str | None = None
    notes: Any = None


class SoftDeletedOut(_Out):
    """Deletes that return ``{\"deleted\": true}`` with optional id."""

    deleted: bool = True
    id: int | None = None


class OfflineExamResultOut(_Out):
    id: int
    exam_id: int
    student_id: int
    student_name: str | None = None
    admission_no: str | None = None
    total_max_marks: float | None = None
    total_obtained: float | None = None
    percentage: float | None = None
    passed: bool | None = None
    processed_at: str | None = None
    subjects: list[Any] | None = None


class ClassListOut(_Out):
    items: list[ClassOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class SectionListOut(_Out):
    items: list[SectionOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class SubjectListOut(_Out):
    items: list[SubjectOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class SessionYearListOut(_Out):
    items: list[SessionYearOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class StudentListOut(_Out):
    items: list[StudentOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class TeacherListOut(_Out):
    items: list[TeacherOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class StaffListOut(_Out):
    items: list[StaffOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class ParentListOut(_Out):
    items: list[ParentOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class TimetableEntryListOut(_Out):
    items: list[TimetableEntryOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class TeacherAssignmentListOut(_Out):
    items: list[TeacherAssignmentOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class HomeworkListOut(_Out):
    items: list[HomeworkOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class HomeworkSubmissionListOut(_Out):
    items: list[HomeworkSubmissionOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class PersonDocumentListOut(_Out):
    items: list[PersonDocumentOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class OfflineExamListOut(_Out):
    items: list[OfflineExamOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class OfflineExamScheduleListOut(_Out):
    items: list[OfflineExamScheduleOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class OfflineExamMarkListOut(_Out):
    items: list[OfflineExamMarkOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class OfflineExamResultListOut(_Out):
    items: list[OfflineExamResultOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class DepartmentListOut(_Out):
    items: list[str] = Field(default_factory=list)


class HomeworkSummaryOut(_Out):
    homework_id: int
    assigned_students: int = 0
    pending_count: int = 0
    submitted_count: int = 0
    late_count: int = 0
    graded_count: int = 0
    notes: Any = None


class OfflineExamResultSummaryOut(_Out):
    exam_id: int
    publish: bool = False
    enrolled_students: int = 0
    processed_students: int = 0
    pending_students: int = 0
    passed_count: int = 0
    failed_count: int = 0
    denominator: str | None = None


class OfflineExamMarkAuditOut(_Out):
    id: int
    previous_marks: float | None = None
    new_marks: float | None = None
    previous_status: str | None = None
    new_status: str | None = None
    reason: str | None = None
    actor_v1_user_id: str | None = None
    created_at: str | None = None


class OfflineExamMarkAuditListOut(RootModel[list[OfflineExamMarkAuditOut]]):
    """Bare JSON array returned by mark-audit list endpoint."""


class WeeklyTimetableDayOut(_Out):
    day: str
    entries: list[TimetableEntryOut | dict[str, Any]] = Field(default_factory=list)


class WeeklyTimetableOut(_Out):
    session_year_id: int | None = None
    class_section_id: int | None = None
    class_id: int | None = None
    section_id: int | None = None
    class_name: str | None = None
    section_name: str | None = None
    teacher_user_id: int | None = None
    teacher_name: str | None = None
    days: list[WeeklyTimetableDayOut | dict[str, Any]] = Field(default_factory=list)


class TeacherDailyTimetableOut(_Out):
    teacher_user_id: int
    teacher_name: str | None = None
    session_year_id: int | None = None
    day: str | None = None
    entries: list[TimetableEntryOut | dict[str, Any]] = Field(default_factory=list)


class TeacherAvailabilityOut(_Out):
    available: bool | None = None
    teacher_user_id: int | None = None
    teacher_name: str | None = None
    conflicts: list[Any] = Field(default_factory=list)
    day: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    session_year_id: int | None = None
    exclude_entry_id: int | None = None


class AcademicSummaryOut(_Out):
    students: int = 0
    teachers: int = 0
    guardians: int = 0
    classes: int = 0
    sections: int = 0
    subjects: int = 0
    exams: int = 0
    fees: int = 0
    announcements: int = 0
    attendance_today: Any = None
    leaves_today: Any = None
    finance_months: list[Any] = Field(default_factory=list)


class AcademicListOut(_Out):
    """Paginated polymorphic ``GET /academics/{resource}`` envelope."""

    items: list[AcademicResourceOut | dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class PeopleListOut(_Out):
    items: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


_BINARY_FILE_RESPONSE = {
    200: {
        "content": {
            "application/octet-stream": {"schema": {"type": "string", "format": "binary"}},
            "image/*": {"schema": {"type": "string", "format": "binary"}},
        },
        "description": "Binary file",
    },
    404: {"description": "Record not found"},
}


def binary_file_response() -> dict:
    return dict(_BINARY_FILE_RESPONSE)
