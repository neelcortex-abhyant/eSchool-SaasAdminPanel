/**
 * Shapes shared by the live and sample-data clients for the School Admin teaching modules:
 * attendance, class timetable, teacher schedules, homework, study materials and online exams.
 * Every record belongs to the signed-in admin's school; the server takes the school from the
 * session, so none of these carry a school_id.
 */
import type { Page } from "@/lib/academics/types";

export type { Page };

/** Where a record sits: session, class section and (for teaching records) subject. */
export type Placement = {
  session_year_id: number;
  class_section_id: number;
  class_id: number;
  class_name: string;
  section_name: string;
};

// ---------- Timetable ----------

export const WEEK_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"] as const;
export type WeekDay = (typeof WEEK_DAYS)[number];

export type TimetableEntry = Placement & {
  id: number;
  subject_id: number;
  subject_name: string;
  teacher_user_id: number;
  teacher_name: string;
  day: WeekDay;
  /** "HH:MM" */
  start_time: string;
  end_time: string;
  note: string | null;
  /** Sample data only; the live backend has no classroom field. */
  room: string | null;
};

export type TimetableInput = {
  session_year_id: number;
  class_section_id: number;
  subject_id: number;
  teacher_user_id: number;
  day: WeekDay;
  start_time: string;
  end_time: string;
  note?: string | null;
  room?: string | null;
};

export type TimetableQuery = {
  page?: number;
  pageSize?: number;
  sessionYearId?: number | "";
  classId?: number | "";
  classSectionId?: number | "";
  day?: WeekDay | "";
};

export type WeekGrid = { day: WeekDay; entries: TimetableEntry[] }[];

export type Availability = {
  available: boolean;
  conflicts: Pick<TimetableEntry, "id" | "day" | "start_time" | "end_time" | "class_name" | "section_name" | "subject_name">[];
};

// ---------- Homework ----------

export type FileMeta = {
  original_filename: string;
  content_type: string;
  size_bytes: number;
  /** A link the browser can open (blob:/data:/auth:), or null when the server has no download route. */
  url: string | null;
};

export type Homework = Placement & {
  id: number;
  subject_id: number;
  subject_name: string;
  teacher_user_id: number;
  teacher_name: string;
  title: string;
  instructions: string | null;
  assigned_date: string;
  /** ISO date-time */
  deadline_at: string;
  max_marks: number | null;
  allow_late: boolean;
  attachments: FileMeta[];
};

export type HomeworkInput = {
  session_year_id: number;
  class_section_id: number;
  subject_id: number;
  teacher_user_id: number;
  title: string;
  instructions: string | null;
  assigned_date: string;
  deadline_at: string;
  max_marks: number | null;
  allow_late: boolean;
};

export type HomeworkQuery = {
  page?: number;
  pageSize?: number;
  q?: string;
  sessionYearId?: number | "";
  classSectionId?: number | "";
  subjectId?: number | "";
  teacherId?: number | "";
};

export type AssignmentStatus = "pending" | "submitted" | "late" | "graded";

export type Submission = {
  id: number;
  homework_id: number;
  student_id: number;
  student_name: string;
  admission_no: string;
  status: AssignmentStatus;
  submitted_at: string | null;
  is_late: boolean;
  text_response: string | null;
  attachments: FileMeta[];
  marks: number | null;
  grade: string | null;
  feedback: string | null;
  evaluated_at: string | null;
};

export type HomeworkSummary = {
  assigned_students: number;
  submitted_count: number;
  graded_count: number;
  late_count: number;
  pending_count: number;
};

export type Evaluation = { marks: number | null; grade: string | null; feedback: string | null };

// ---------- Study materials ----------

export type MaterialType = "file" | "video_link" | "document_reference";

export type Material = Placement & {
  id: number;
  subject_id: number;
  subject_name: string;
  teacher_user_id: number;
  teacher_name: string;
  resource_type: MaterialType;
  title: string;
  description: string | null;
  chapter: string | null;
  topic: string | null;
  external_url: string | null;
  file: FileMeta | null;
  created_at: string;
};

export type MaterialInput = {
  session_year_id: number;
  class_section_id: number;
  subject_id: number;
  teacher_user_id: number;
  resource_type: MaterialType;
  title: string;
  description: string | null;
  chapter: string | null;
  topic: string | null;
  external_url: string | null;
};

export type MaterialQuery = {
  page?: number;
  pageSize?: number;
  q?: string;
  sessionYearId?: number | "";
  classSectionId?: number | "";
  subjectId?: number | "";
  resourceType?: MaterialType | "";
};

// ---------- Online exams ----------

export type ExamStatus = "draft" | "published" | "closed";

export type OnlineExam = Placement & {
  id: number;
  subject_id: number;
  subject_name: string;
  teacher_user_id: number;
  title: string;
  instructions: string | null;
  duration_minutes: number;
  total_marks: number;
  passing_marks: number;
  /** ISO date-times */
  available_from: string;
  available_until: string;
  status: ExamStatus;
  results_published: boolean;
};

export type OnlineExamInput = {
  session_year_id: number;
  class_section_id: number;
  subject_id: number;
  teacher_user_id: number;
  title: string;
  instructions: string | null;
  duration_minutes: number;
  total_marks: number;
  passing_marks: number;
  available_from: string;
  available_until: string;
};

export type OnlineExamQuery = {
  page?: number;
  pageSize?: number;
  q?: string;
  sessionYearId?: number | "";
  classSectionId?: number | "";
  subjectId?: number | "";
  status?: ExamStatus | "";
};

export type Choice = { id?: number; choice_text: string; is_correct: boolean };

export type Question = {
  id: number;
  question_text: string;
  topic: string | null;
  marks: number;
  sort_order: number;
  choices: Choice[];
};

export type QuestionInput = Omit<Question, "id">;

export type ExamDetail = OnlineExam & {
  questions: Question[];
  /** Attempts exist on a published or closed exam, so questions can't change. */
  locked: boolean;
  attempt_count: number;
};

export type AttemptStatus = "in_progress" | "submitted" | "expired" | "evaluated";

export type Attempt = {
  id: number;
  student_id: number;
  student_name: string;
  admission_no: string;
  status: AttemptStatus;
  started_at: string | null;
  submitted_at: string | null;
  score: number | null;
  percentage: number | null;
  passed: boolean | null;
};

export type AttemptAnswer = { question_text: string; marks: number; chosen: string | null; correct: string | null; awarded: number | null };

export type AttemptDetail = Attempt & { answers: AttemptAnswer[] };

/** A question saved for reuse across exams (sample data only). */
export type BankQuestion = Question & { subject_name: string | null };

// ---------- Attendance ----------

export type AttendanceStatus = "present" | "absent" | "late" | "leave";

export type AttendanceRecord = {
  id: number;
  student_id: number;
  student_name: string;
  admission_no: string;
  class_section_id: number;
  session_year_id: number;
  date: string;
  status: AttendanceStatus;
  remark: string | null;
  /** Earlier values, newest first (sample data only). */
  history: { status: AttendanceStatus; remark: string | null; changed_at: string }[];
};

export type AttendanceMark = { student_id: number; status: AttendanceStatus; remark?: string | null };

export type AttendanceQuery = {
  sessionYearId?: number | "";
  classSectionId?: number | "";
  studentId?: number | "";
  from?: string;
  to?: string;
};

export type AttendanceLock = { class_section_id: number; date: string; locked: boolean };
