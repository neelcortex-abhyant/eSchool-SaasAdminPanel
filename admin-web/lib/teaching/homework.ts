/**
 * Homework, submissions and evaluation.
 * Live: /school-admin/homework (list, create, get, PATCH, DELETE), /homework/{id}/attachments
 * (file upload), /homework/{id}/submissions, /homework/{id}/summary,
 * /homework-submissions/{id} and /homework-submissions/{id}/evaluation.
 * The live backend has no download route for homework or submission files, so those show by
 * name only. Its submissions list holds students who submitted; students with no submission
 * are listed as pending from the section's student list.
 */
import { listAll } from "@/lib/academics";
import { peopleService } from "@/lib/people";
import { allPages, get, num, optNum, optStr, pageOf, send, str, upload, type Raw } from "@/lib/teaching/client";
import { isLive } from "@/lib/teaching/mode";
import { placementOf, sectionMap as sectionNames, subjectName, teacherName } from "@/lib/teaching/lookups";
import { db, delay, invalid, matches, nextId, notFound, nowIso, paginate, save } from "@/lib/teaching/store";
import type {
  AssignmentStatus,
  Evaluation,
  FileMeta,
  Homework,
  HomeworkInput,
  HomeworkQuery,
  HomeworkSummary,
  Page,
  Placement,
  Submission,
} from "@/lib/teaching/types";

export interface HomeworkService {
  list(query?: HomeworkQuery): Promise<Page<Homework>>;
  get(id: number): Promise<Homework>;
  create(input: HomeworkInput): Promise<Homework>;
  update(id: number, input: HomeworkInput): Promise<Homework>;
  remove(id: number): Promise<void>;
  addAttachment(id: number, file: File): Promise<void>;
  submissions(homework: Homework): Promise<Submission[]>;
  summary(id: number): Promise<HomeworkSummary>;
  evaluate(submissionId: number, evaluation: Evaluation): Promise<Submission>;
}

const BASE = "/school-admin";

function fileOf(row: Raw): FileMeta {
  return { original_filename: str(row.original_filename, "file"), content_type: str(row.content_type), size_bytes: num(row.size_bytes), url: null };
}

function homeworkOf(row: Raw, sections: Map<number, Placement>): Homework {
  const place = sections.get(num(row.class_section_id));
  return {
    id: num(row.id),
    session_year_id: num(row.session_year_id),
    class_section_id: num(row.class_section_id),
    class_id: place?.class_id ?? 0,
    class_name: place?.class_name ?? `Section #${num(row.class_section_id)}`,
    section_name: place?.section_name ?? "",
    subject_id: num(row.subject_id),
    subject_name: str(row.subject_name),
    teacher_user_id: num(row.teacher_user_id),
    teacher_name: str(row.teacher_name),
    title: str(row.title),
    instructions: optStr(row.instructions),
    assigned_date: str(row.assigned_date).slice(0, 10),
    deadline_at: str(row.deadline_at),
    max_marks: optNum(row.max_marks),
    allow_late: Boolean(row.allow_late),
    attachments: Array.isArray(row.attachments) ? (row.attachments as Raw[]).map(fileOf) : [],
  };
}

function statusOf(row: Raw): AssignmentStatus {
  const status = str(row.assignment_status || row.status).toLowerCase();
  if (status === "graded") return "graded";
  if (row.is_late || status === "late") return "late";
  if (status === "submitted") return "submitted";
  return "pending";
}

function submissionOf(row: Raw): Submission {
  return {
    id: num(row.id),
    homework_id: num(row.homework_id),
    student_id: num(row.student_id),
    student_name: str(row.student_name),
    admission_no: str(row.admission_no),
    status: statusOf(row),
    submitted_at: optStr(row.submitted_at),
    is_late: Boolean(row.is_late),
    text_response: optStr(row.text_response),
    attachments: Array.isArray(row.attachments) ? (row.attachments as Raw[]).map(fileOf) : [],
    marks: optNum(row.marks),
    grade: optStr(row.grade),
    feedback: optStr(row.feedback),
    evaluated_at: optStr(row.evaluated_at),
  };
}

function body(input: HomeworkInput) {
  return {
    session_year_id: input.session_year_id,
    class_section_id: input.class_section_id,
    subject_id: input.subject_id,
    teacher_user_id: input.teacher_user_id,
    title: input.title.trim(),
    instructions: input.instructions?.trim() || null,
    assigned_date: input.assigned_date,
    deadline_at: input.deadline_at,
    max_marks: input.max_marks,
    allow_late: input.allow_late,
  };
}

/** Students of a section who should hand the homework in. */
async function roster(sessionYearId: number, classSectionId: number) {
  return listAll((page) => peopleService("students").listStudents({ page, pageSize: 50, sessionYearId, classSectionId, status: "1" }));
}

function pendingRow(homeworkId: number, student: { id: number; name: string; admission_no: string }): Submission {
  return {
    id: -student.id,
    homework_id: homeworkId,
    student_id: student.id,
    student_name: student.name,
    admission_no: student.admission_no,
    status: "pending",
    submitted_at: null,
    is_late: false,
    text_response: null,
    attachments: [],
    marks: null,
    grade: null,
    feedback: null,
    evaluated_at: null,
  };
}

export const liveHomework: HomeworkService = {
  async list(query = {}) {
    const [data, sections] = await Promise.all([
      get(`${BASE}/homework`, {
        page: query.page ?? 1,
        page_size: Math.min(query.pageSize ?? 20, 50),
        q: query.q?.trim(),
        session_year_id: query.sessionYearId,
        class_section_id: query.classSectionId,
        subject_id: query.subjectId,
        teacher_user_id: query.teacherId,
      }, "Unable to load homework."),
      sectionNames(),
    ]);
    return pageOf(data, (row) => homeworkOf(row, sections));
  },
  async get(id) {
    const [row, sections] = await Promise.all([get(`${BASE}/homework/${id}`, {}, "Unable to load this homework."), sectionNames()]);
    return homeworkOf(row, sections);
  },
  async create(input) {
    const [row, sections] = await Promise.all([send("POST", `${BASE}/homework`, { ...body(input), attachments: [] }, "Unable to add the homework."), sectionNames()]);
    return homeworkOf(row, sections);
  },
  async update(id, input) {
    const [row, sections] = await Promise.all([send("PATCH", `${BASE}/homework/${id}`, body(input), "Unable to save the homework."), sectionNames()]);
    return homeworkOf(row, sections);
  },
  async remove(id) {
    await send("DELETE", `${BASE}/homework/${id}`, undefined, "Unable to delete the homework.");
  },
  async addAttachment(id, file) {
    const form = new FormData();
    form.set("file", file);
    await upload(`${BASE}/homework/${id}/attachments`, form, `Unable to upload ${file.name}.`);
  },
  async submissions(homework) {
    const [rows, students] = await Promise.all([
      allPages(`${BASE}/homework/${homework.id}/submissions`, {}, "Unable to load submissions."),
      roster(homework.session_year_id, homework.class_section_id).catch(() => []),
    ]);
    const submitted = rows.map(submissionOf);
    const handedIn = new Set(submitted.map((row) => row.student_id));
    const pending = students.filter((student) => !handedIn.has(student.id)).map((student) => pendingRow(homework.id, student));
    return [...submitted, ...pending];
  },
  async summary(id) {
    const data = await get(`${BASE}/homework/${id}/summary`, {}, "Unable to load the summary.");
    return {
      assigned_students: num(data.assigned_students),
      submitted_count: num(data.submitted_count),
      graded_count: num(data.graded_count),
      late_count: num(data.late_count),
      pending_count: num(data.pending_count),
    };
  },
  async evaluate(submissionId, evaluation) {
    return submissionOf(await send("PATCH", `${BASE}/homework-submissions/${submissionId}/evaluation`, evaluation, "Unable to save the evaluation."));
  },
};

// ---------- sample data ----------

type HomeworkRow = Homework;

function homeworkRows(): HomeworkRow[] {
  return db().homework as HomeworkRow[];
}

function submissionRows(): Submission[] {
  return db().submissions as Submission[];
}

function check(input: HomeworkInput) {
  const errors: Record<string, string> = {};
  if (!input.session_year_id) errors.session_year_id = "Choose an academic session.";
  if (!input.class_section_id) errors.class_section_id = "Choose a section.";
  if (!input.subject_id) errors.subject_id = "Choose a subject.";
  if (!input.teacher_user_id) errors.teacher_user_id = "Choose a teacher.";
  if (!input.title.trim()) errors.title = "Enter a title.";
  if (!input.assigned_date) errors.assigned_date = "Enter the assigned date.";
  if (!input.deadline_at) errors.deadline_at = "Enter the deadline.";
  else if (input.assigned_date && input.deadline_at.slice(0, 10) < input.assigned_date) errors.deadline_at = "The deadline can't be before the assigned date.";
  if (input.max_marks !== null && (Number.isNaN(input.max_marks) || input.max_marks <= 0)) errors.max_marks = "Maximum marks must be more than 0.";
  if (Object.keys(errors).length) invalid(errors);
}

async function buildHomework(input: HomeworkInput, id: number, attachments: FileMeta[]): Promise<HomeworkRow> {
  const [placement, subject, teacher] = await Promise.all([
    placementOf(input.session_year_id, input.class_section_id),
    subjectName(input.subject_id),
    teacherName(input.teacher_user_id),
  ]);
  return { id, ...placement, ...body(input), subject_name: subject, teacher_name: teacher, attachments };
}

function readFile(file: File): Promise<string | null> {
  if (file.size > 400 * 1024) return Promise.resolve(URL.createObjectURL(file));
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : null);
    reader.onerror = () => resolve(null);
    reader.readAsDataURL(file);
  });
}

export const mockHomework: HomeworkService = {
  async list(query = {}) {
    const list = homeworkRows()
      .filter((row) => !query.sessionYearId || row.session_year_id === query.sessionYearId)
      .filter((row) => !query.classSectionId || row.class_section_id === query.classSectionId)
      .filter((row) => !query.subjectId || row.subject_id === query.subjectId)
      .filter((row) => !query.teacherId || row.teacher_user_id === query.teacherId)
      .filter((row) => matches(query.q, row.title, row.subject_name, row.teacher_name))
      .sort((a, b) => b.assigned_date.localeCompare(a.assigned_date) || b.id - a.id);
    return delay(paginate(list, query.page, query.pageSize));
  },
  async get(id) {
    return delay(homeworkRows().find((row) => row.id === id) ?? notFound("Homework"));
  },
  async create(input) {
    check(input);
    const row = await buildHomework(input, nextId(homeworkRows()), []);
    homeworkRows().push(row);
    save();
    return delay(row);
  },
  async update(id, input) {
    const index = homeworkRows().findIndex((row) => row.id === id);
    if (index < 0) notFound("Homework");
    check(input);
    const row = await buildHomework(input, id, homeworkRows()[index].attachments);
    homeworkRows()[index] = row;
    save();
    return delay(row);
  },
  async remove(id) {
    const db0 = db();
    if (!homeworkRows().some((row) => row.id === id)) notFound("Homework");
    db0.homework = homeworkRows().filter((row) => row.id !== id);
    db0.submissions = submissionRows().filter((row) => row.homework_id !== id);
    save();
    await delay(null);
  },
  async addAttachment(id, file) {
    const row = homeworkRows().find((item) => item.id === id) ?? notFound("Homework");
    if (row.attachments.length >= 10) invalid({ file: "A homework can have up to 10 attachments." });
    row.attachments.push({ original_filename: file.name, content_type: file.type, size_bytes: file.size, url: await readFile(file) });
    save();
  },
  async submissions(homework) {
    const submitted = submissionRows().filter((row) => row.homework_id === homework.id);
    const students = await roster(homework.session_year_id, homework.class_section_id).catch(() => []);
    const known = new Set(submitted.map((row) => row.student_id));
    const extra = students.filter((student) => !known.has(student.id)).map((student) => pendingRow(homework.id, student));
    return delay([...submitted, ...extra]);
  },
  async summary(id) {
    const list = submissionRows().filter((row) => row.homework_id === id);
    return delay({
      assigned_students: list.length,
      submitted_count: list.filter((row) => row.status !== "pending").length,
      graded_count: list.filter((row) => row.status === "graded").length,
      late_count: list.filter((row) => row.is_late).length,
      pending_count: list.filter((row) => row.status === "pending").length,
    });
  },
  async evaluate(submissionId, evaluation) {
    const row = submissionRows().find((item) => item.id === submissionId) ?? notFound("Submission");
    if (row.status === "pending") invalid({ marks: "This student hasn't submitted yet." });
    const homework = homeworkRows().find((item) => item.id === row.homework_id);
    if (evaluation.marks !== null && homework?.max_marks !== null && homework && evaluation.marks > (homework.max_marks ?? 0)) {
      invalid({ marks: `Marks can't be more than ${homework.max_marks}.` });
    }
    Object.assign(row, evaluation, { status: "graded", evaluated_at: nowIso() });
    save();
    return delay(row);
  },
};

export function homeworkService(): HomeworkService {
  return isLive("homework") ? liveHomework : mockHomework;
}
