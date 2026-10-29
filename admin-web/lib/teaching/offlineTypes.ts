/** Offline (written) exams: the exam, its subject timetable, marks and processed results. */
import type { Placement } from "@/lib/teaching/types";

export type OfflineExamRow = {
  id: number;
  name: string;
  description: string | null;
  session_year_id: number;
  class_section_id: number;
  exam_type: string | null;
  /** YYYY-MM-DD */
  exam_date: string | null;
  /** Results are visible to students and parents; marks can't change while published. */
  publish: boolean;
  results_processed_at: string | null;
};

export type OfflineExam = OfflineExamRow & Placement;

export type OfflineExamInput = {
  name: string;
  description: string | null;
  session_year_id: number;
  class_section_id: number;
  exam_type: string | null;
  exam_date: string | null;
};

export type OfflineExamQuery = {
  page?: number;
  pageSize?: number;
  q?: string;
  sessionYearId?: number | "";
  classSectionId?: number | "";
};

export type OfflineSchedule = {
  id: number;
  exam_id: number;
  session_year_id: number;
  class_section_id: number;
  subject_id: number;
  subject_name: string | null;
  teacher_user_id: number | null;
  exam_date: string;
  /** "HH:MM" or null */
  start_time: string | null;
  end_time: string | null;
  max_marks: number;
  passing_marks: number;
};

export type OfflineScheduleInput = {
  subject_id: number;
  teacher_user_id: number | null;
  exam_date: string;
  start_time: string | null;
  end_time: string | null;
  max_marks: number;
  passing_marks: number;
};

export type OfflineExamDetail = OfflineExam & { schedules: OfflineSchedule[] };

export type MarkStatus = "present" | "absent" | "withheld";

export type OfflineMark = {
  id: number;
  exam_id: number;
  schedule_id: number;
  student_id: number;
  student_name: string;
  admission_no: string | null;
  marks_obtained: number | null;
  status: MarkStatus;
};

export type MarkInput = { student_id: number; marks_obtained: number | null; status: MarkStatus; reason?: string | null };

export type OfflineAudit = {
  id: number;
  mark_id: number;
  previous_marks: number | null;
  new_marks: number | null;
  previous_status: string | null;
  new_status: string | null;
  reason: string | null;
  created_at: string;
};

export type ResultSubject = {
  schedule_id: number;
  subject_id: number;
  subject_name: string | null;
  status: MarkStatus;
  marks_obtained: number | null;
  max_marks: number;
  passing_marks?: number;
  passed: boolean | null;
  included: boolean;
};

export type OfflineResult = {
  id: number;
  exam_id: number;
  student_id: number;
  student_name: string;
  admission_no: string | null;
  total_max_marks: number;
  total_obtained: number;
  percentage: number;
  passed: boolean;
  processed_at: string | null;
  subjects: ResultSubject[];
};

export type ResultSummary = {
  publish: boolean;
  enrolled_students: number;
  processed_students: number;
  pending_students: number;
  passed_count: number;
  failed_count: number;
};

export type ProcessOutcome = { processed_students: number; pending_students: number; enrolled_students: number };
