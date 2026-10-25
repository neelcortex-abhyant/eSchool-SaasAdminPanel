/**
 * Offline exams.
 * Live: /school-admin/offline-exams (list, create, get with schedules, PATCH incl. publish,
 * DELETE), /offline-exams/{id}/schedules (add a subject paper), /offline-exam-schedules (list),
 * /offline-exam-schedules/{id}/marks (one mark, with a reason for corrections) and /marks/bulk
 * (up to 200), /offline-exam-marks (list) and /{id}/audits, /offline-exams/{id}/process-results,
 * /results and /results/summary. The server has no route to edit or remove a subject paper.
 * Rules the server enforces (and the sample data repeats): marks can't change while results are
 * published; a correction after results were processed needs a reason; an exam with marks
 * can't move class or be deleted; papers for one class can't overlap.
 */
import { listAll } from "@/lib/academics";
import { peopleService } from "@/lib/people";
import { allPages, get, hhmm, notAvailable, num, optNum, optStr, pageOf, send, str, type Raw } from "@/lib/teaching/client";
import { isLive } from "@/lib/teaching/mode";
import { placementOf, sectionMap, subjectName } from "@/lib/teaching/lookups";
import { conflict, db, delay, invalid, matches, nextId, notFound, nowIso, paginate, save } from "@/lib/teaching/store";
import { AcademicApiError } from "@/lib/academics/errors";
import type { Page, Placement } from "@/lib/teaching/types";
import type {
  MarkInput,
  MarkStatus,
  OfflineAudit,
  OfflineExam,
  OfflineExamDetail,
  OfflineExamInput,
  OfflineExamQuery,
  OfflineExamRow,
  OfflineMark,
  OfflineResult,
  OfflineSchedule,
  OfflineScheduleInput,
  ProcessOutcome,
  ResultSubject,
  ResultSummary,
} from "@/lib/teaching/offlineTypes";

export type SaveMarksOutcome = { saved: number; failures: { student_id: number; message: string }[] };

export interface OfflineExamService {
  list(query?: OfflineExamQuery): Promise<Page<OfflineExam>>;
  get(id: number): Promise<OfflineExamDetail>;
  create(input: OfflineExamInput): Promise<OfflineExam>;
  update(id: number, input: OfflineExamInput): Promise<OfflineExam>;
  setPublish(id: number, publish: boolean): Promise<OfflineExam>;
  remove(id: number): Promise<void>;
  addSchedule(examId: number, input: OfflineScheduleInput): Promise<OfflineSchedule>;
  /** The server has no route for these yet; the live client says so (sample data only). */
  updateSchedule(scheduleId: number, input: OfflineScheduleInput): Promise<OfflineSchedule>;
  removeSchedule(scheduleId: number): Promise<void>;
  schedules(query: { sessionYearId?: number | ""; classSectionId?: number | ""; examId?: number }): Promise<OfflineSchedule[]>;
  marks(scheduleId: number): Promise<OfflineMark[]>;
  /** New marks go in one bulk request; corrections after processing go one by one with their reason. */
  saveMarks(exam: OfflineExamDetail, scheduleId: number, items: MarkInput[], existing: OfflineMark[]): Promise<SaveMarksOutcome>;
  audits(markId: number): Promise<OfflineAudit[]>;
  processResults(examId: number): Promise<ProcessOutcome>;
  results(examId: number): Promise<OfflineResult[]>;
  summary(examId: number): Promise<ResultSummary>;
}

const BASE = "/school-admin";

export const MARK_STATUS_LABEL: Record<MarkStatus, string> = { present: "Present", absent: "Absent", withheld: "Withheld" };

function examOf(row: Raw, sections: Map<number, Placement>): OfflineExam {
  const csId = num(row.class_section_id);
  const place = sections.get(csId);
  return {
    id: num(row.id),
    name: str(row.name),
    description: optStr(row.description),
    session_year_id: num(row.session_year_id),
    class_section_id: csId,
    class_id: place?.class_id ?? num(row.class_id),
    class_name: place?.class_name ?? `Section #${csId}`,
    section_name: place?.section_name ?? "",
    exam_type: optStr(row.exam_type),
    exam_date: optStr(row.exam_date)?.slice(0, 10) ?? null,
    publish: Boolean(row.publish),
    results_processed_at: optStr(row.results_processed_at),
  };
}

function scheduleOf(row: Raw): OfflineSchedule {
  return {
    id: num(row.id),
    exam_id: num(row.exam_id),
    session_year_id: num(row.session_year_id),
    class_section_id: num(row.class_section_id),
    subject_id: num(row.subject_id),
    subject_name: optStr(row.subject_name),
    teacher_user_id: optNum(row.teacher_user_id),
    exam_date: str(row.exam_date).slice(0, 10),
    start_time: row.start_time ? hhmm(row.start_time) : null,
    end_time: row.end_time ? hhmm(row.end_time) : null,
    max_marks: num(row.max_marks),
    passing_marks: num(row.passing_marks),
  };
}

function markOf(row: Raw): OfflineMark {
  return {
    id: num(row.id),
    exam_id: num(row.exam_id),
    schedule_id: num(row.schedule_id),
    student_id: num(row.student_id),
    student_name: str(row.student_name),
    admission_no: optStr(row.admission_no),
    marks_obtained: optNum(row.marks_obtained),
    status: str(row.status, "present") as MarkStatus,
  };
}

function resultOf(row: Raw): OfflineResult {
  return {
    id: num(row.id),
    exam_id: num(row.exam_id),
    student_id: num(row.student_id),
    student_name: str(row.student_name),
    admission_no: optStr(row.admission_no),
    total_max_marks: num(row.total_max_marks),
    total_obtained: num(row.total_obtained),
    percentage: num(row.percentage),
    passed: Boolean(row.passed),
    processed_at: optStr(row.processed_at),
    subjects: Array.isArray(row.subjects) ? (row.subjects as ResultSubject[]) : [],
  };
}

function examBody(input: OfflineExamInput) {
  return {
    name: input.name.trim(),
    description: input.description?.trim() || null,
    session_year_id: input.session_year_id,
    class_section_id: input.class_section_id,
    exam_type: input.exam_type?.trim() || null,
    exam_date: input.exam_date || null,
  };
}

function scheduleBody(input: OfflineScheduleInput) {
  return {
    subject_id: input.subject_id,
    teacher_user_id: input.teacher_user_id || null,
    exam_date: input.exam_date,
    start_time: input.start_time || null,
    end_time: input.end_time || null,
    max_marks: input.max_marks,
    passing_marks: input.passing_marks,
  };
}

function checkExam(input: OfflineExamInput) {
  const errors: Record<string, string> = {};
  if (!input.name.trim()) errors.name = "Enter the exam name.";
  if (!input.session_year_id) errors.session_year_id = "Choose an academic session.";
  if (!input.class_section_id) errors.class_section_id = "Choose a section.";
  if (Object.keys(errors).length) invalid(errors);
}

/** The same checks the server makes on a subject paper. */
export function scheduleProblems(input: OfflineScheduleInput): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!input.subject_id) errors.subject_id = "Choose a subject.";
  if (!input.exam_date) errors.exam_date = "Choose the date.";
  if (Boolean(input.start_time) !== Boolean(input.end_time)) errors.end_time = "Enter both times, or neither.";
  else if (input.start_time && input.end_time && input.end_time <= input.start_time) errors.end_time = "End time must be after the start time.";
  if (!(input.max_marks > 0)) errors.max_marks = "Maximum marks must be more than 0.";
  if (!(input.passing_marks >= 0) || input.passing_marks > input.max_marks) errors.passing_marks = "Passing marks must be between 0 and the maximum.";
  return errors;
}

/** The same checks the server makes on one mark. */
export function markProblem(item: MarkInput, maxMarks: number): string {
  if (item.status === "present") {
    if (item.marks_obtained === null || Number.isNaN(item.marks_obtained)) return "Enter the marks, or mark the student absent.";
    if (item.marks_obtained < 0 || item.marks_obtained > maxMarks) return `Marks must be between 0 and ${maxMarks}.`;
  }
  return "";
}

export const liveOffline: OfflineExamService = {
  async list(query = {}) {
    const [data, sections] = await Promise.all([
      get(`${BASE}/offline-exams`, {
        page: query.page ?? 1,
        page_size: Math.min(query.pageSize ?? 20, 50),
        q: query.q?.trim(),
        session_year_id: query.sessionYearId,
        class_section_id: query.classSectionId,
      }, "Unable to load offline exams."),
      sectionMap(),
    ]);
    return pageOf(data, (row) => examOf(row, sections));
  },
  async get(id) {
    const [row, sections] = await Promise.all([get(`${BASE}/offline-exams/${id}`, {}, "Unable to load this exam."), sectionMap()]);
    const schedules = (Array.isArray(row.schedules) ? (row.schedules as Raw[]) : []).map(scheduleOf);
    return { ...examOf(row, sections), schedules };
  },
  async create(input) {
    checkExam(input);
    const [row, sections] = await Promise.all([send("POST", `${BASE}/offline-exams`, examBody(input), "Unable to create the exam."), sectionMap()]);
    return examOf(row, sections);
  },
  async update(id, input) {
    checkExam(input);
    const [row, sections] = await Promise.all([send("PATCH", `${BASE}/offline-exams/${id}`, examBody(input), "Unable to save the exam."), sectionMap()]);
    return examOf(row, sections);
  },
  async setPublish(id, publish) {
    const [row, sections] = await Promise.all([send("PATCH", `${BASE}/offline-exams/${id}`, { publish }, "Unable to change publishing."), sectionMap()]);
    return examOf(row, sections);
  },
  async remove(id) {
    await send("DELETE", `${BASE}/offline-exams/${id}`, undefined, "Unable to delete the exam.");
  },
  async addSchedule(examId, input) {
    const errors = scheduleProblems(input);
    if (Object.keys(errors).length) invalid(errors);
    return scheduleOf(await send("POST", `${BASE}/offline-exams/${examId}/schedules`, scheduleBody(input), "Unable to add the paper."));
  },
  async updateSchedule() {
    return notAvailable("Changing a paper isn't available on the school's server yet. Delete isn't either; ask the server team to add it.");
  },
  async removeSchedule() {
    return notAvailable("Removing a paper isn't available on the school's server yet.");
  },
  async schedules(query) {
    const rows = await allPages(`${BASE}/offline-exam-schedules`, {
      session_year_id: query.sessionYearId,
      class_section_id: query.classSectionId,
      exam_id: query.examId,
    }, "Unable to load the exam timetable.");
    return rows.map(scheduleOf).sort((a, b) => a.exam_date.localeCompare(b.exam_date) || (a.start_time ?? "").localeCompare(b.start_time ?? ""));
  },
  async marks(scheduleId) {
    return (await allPages(`${BASE}/offline-exam-marks`, { schedule_id: scheduleId }, "Unable to load marks.")).map(markOf);
  },
  async saveMarks(exam, scheduleId, items, existing) {
    const known = new Set(existing.map((mark) => mark.student_id));
    // After processing, a changed mark needs a reason, which only the single-mark route takes.
    const single = items.filter((item) => exam.results_processed_at && known.has(item.student_id));
    const bulk = items.filter((item) => !single.includes(item));
    const failures: SaveMarksOutcome["failures"] = [];
    let saved = 0;
    for (let start = 0; start < bulk.length; start += 200) {
      const chunk = bulk.slice(start, start + 200);
      try {
        await send("POST", `${BASE}/offline-exam-schedules/${scheduleId}/marks/bulk`, {
          items: chunk.map((item) => ({ student_id: item.student_id, marks_obtained: item.status === "present" ? item.marks_obtained : null, status: item.status })),
        }, "Unable to save marks.");
        saved += chunk.length;
      } catch (caught) {
        // The bulk route saves all or nothing; report the server's sentence on every row.
        const message = caught instanceof Error ? caught.message : "Not saved";
        chunk.forEach((item) => failures.push({ student_id: item.student_id, message }));
      }
    }
    for (const item of single) {
      try {
        await send("POST", `${BASE}/offline-exam-schedules/${scheduleId}/marks`, {
          student_id: item.student_id,
          marks_obtained: item.status === "present" ? item.marks_obtained : null,
          status: item.status,
          reason: item.reason?.trim() || null,
        }, "Unable to save the mark.");
        saved += 1;
      } catch (caught) {
        failures.push({ student_id: item.student_id, message: caught instanceof Error ? caught.message : "Not saved" });
      }
    }
    return { saved, failures };
  },
  async audits(markId) {
    const rows = await get<Raw[]>(`${BASE}/offline-exam-marks/${markId}/audits`, {}, "Unable to load the change history.");
    return (Array.isArray(rows) ? rows : []).map((row) => ({
      id: num(row.id),
      mark_id: markId,
      previous_marks: optNum(row.previous_marks),
      new_marks: optNum(row.new_marks),
      previous_status: optStr(row.previous_status),
      new_status: optStr(row.new_status),
      reason: optStr(row.reason),
      created_at: str(row.created_at),
    }));
  },
  async processResults(examId) {
    const data = await send("POST", `${BASE}/offline-exams/${examId}/process-results`, {}, "Unable to process results.");
    return { processed_students: num(data.processed_students), pending_students: num(data.pending_students), enrolled_students: num(data.enrolled_students) };
  },
  async results(examId) {
    return (await allPages(`${BASE}/offline-exams/${examId}/results`, {}, "Unable to load results.")).map(resultOf);
  },
  async summary(examId) {
    const data = await get(`${BASE}/offline-exams/${examId}/results/summary`, {}, "Unable to load the result summary.");
    return {
      publish: Boolean(data.publish),
      enrolled_students: num(data.enrolled_students),
      processed_students: num(data.processed_students),
      pending_students: num(data.pending_students),
      passed_count: num(data.passed_count),
      failed_count: num(data.failed_count),
    };
  },
};

// ---------- sample data ----------

const exams = () => db().offlineExams;
const schedules = () => db().offlineSchedules;
const marks = () => db().offlineMarks;
const results = () => db().offlineResults;

function findExam(id: number): OfflineExamRow {
  return exams().find((row) => row.id === id) ?? notFound("Offline exam");
}

async function withPlacement(row: OfflineExamRow): Promise<OfflineExam> {
  return { ...row, ...(await placementOf(row.session_year_id, row.class_section_id)) };
}

async function enrolled(row: { session_year_id: number; class_section_id: number }) {
  const students = await listAll((page) =>
    peopleService("students").listStudents({ page, pageSize: 50, sessionYearId: row.session_year_id, classSectionId: row.class_section_id, status: "1" }),
  );
  return students;
}

function overlaps(a: OfflineSchedule, b: OfflineScheduleInput) {
  if (a.exam_date !== b.exam_date) return false;
  if (!a.start_time || !a.end_time || !b.start_time || !b.end_time) return true;
  return a.start_time < b.end_time && b.start_time < a.end_time;
}

export const mockOffline: OfflineExamService = {
  async list(query = {}) {
    const rows = exams()
      .filter((row) => !query.sessionYearId || row.session_year_id === query.sessionYearId)
      .filter((row) => !query.classSectionId || row.class_section_id === query.classSectionId)
      .filter((row) => matches(query.q, row.name, row.exam_type, row.description))
      .sort((a, b) => (b.exam_date ?? "").localeCompare(a.exam_date ?? "") || b.id - a.id);
    const page = paginate(rows, query.page, query.pageSize);
    return delay({ ...page, items: await Promise.all(page.items.map(withPlacement)) });
  },
  async get(id) {
    const row = findExam(id);
    const list = schedules().filter((item) => item.exam_id === id).sort((a, b) => a.exam_date.localeCompare(b.exam_date) || a.id - b.id);
    return delay({ ...(await withPlacement(row)), schedules: list });
  },
  async create(input) {
    checkExam(input);
    const row: OfflineExamRow = { id: nextId(exams()), ...examBody(input), publish: false, results_processed_at: null };
    exams().push(row);
    save();
    return delay(await withPlacement(row));
  },
  async update(id, input) {
    checkExam(input);
    const row = findExam(id);
    const hasMarks = marks().some((mark) => mark.exam_id === id);
    if (hasMarks && (row.session_year_id !== input.session_year_id || row.class_section_id !== input.class_section_id)) {
      invalid({ class_section_id: "Cannot change session/class-section after marks exist" });
    }
    Object.assign(row, examBody(input));
    schedules().filter((item) => item.exam_id === id).forEach((item) => Object.assign(item, { session_year_id: row.session_year_id, class_section_id: row.class_section_id }));
    save();
    return delay(await withPlacement(row));
  },
  async setPublish(id, publish) {
    const row = findExam(id);
    row.publish = publish;
    save();
    return delay(await withPlacement(row));
  },
  async remove(id) {
    const row = findExam(id);
    if (row.publish) throw new AcademicApiError(422, "Unpublish the exam before deleting");
    if (marks().some((mark) => mark.exam_id === id)) throw new AcademicApiError(422, "Cannot delete an exam that already has marks; unpublish and archive instead");
    db().offlineExams = exams().filter((item) => item.id !== id);
    db().offlineSchedules = schedules().filter((item) => item.exam_id !== id);
    save();
    await delay(null);
  },
  async addSchedule(examId, input) {
    const exam = findExam(examId);
    const errors = scheduleProblems(input);
    if (Object.keys(errors).length) invalid(errors);
    const sameClass = schedules().filter((item) => item.class_section_id === exam.class_section_id && item.session_year_id === exam.session_year_id);
    if (sameClass.some((item) => overlaps(item, input))) conflict("Schedule conflicts with another exam for this class-section");
    const row: OfflineSchedule = {
      id: nextId(schedules()),
      exam_id: examId,
      session_year_id: exam.session_year_id,
      class_section_id: exam.class_section_id,
      ...scheduleBody(input),
      subject_name: await subjectName(input.subject_id),
    };
    schedules().push(row);
    save();
    return delay(row);
  },
  async updateSchedule(scheduleId, input) {
    const row = schedules().find((item) => item.id === scheduleId) ?? notFound("Exam paper");
    if (marks().some((mark) => mark.schedule_id === scheduleId) && (input.subject_id !== row.subject_id || input.max_marks < Math.max(0, ...marks().filter((mark) => mark.schedule_id === scheduleId).map((mark) => mark.marks_obtained ?? 0)))) {
      conflict("Marks are already entered for this paper, so its subject can't change and its maximum can't go below the highest mark.");
    }
    const errors = scheduleProblems(input);
    if (Object.keys(errors).length) invalid(errors);
    const others = schedules().filter((item) => item.id !== scheduleId && item.class_section_id === row.class_section_id && item.session_year_id === row.session_year_id);
    if (others.some((item) => overlaps(item, input))) conflict("Schedule conflicts with another exam for this class-section");
    Object.assign(row, scheduleBody(input), { subject_name: await subjectName(input.subject_id) });
    save();
    return delay(row);
  },
  async removeSchedule(scheduleId) {
    if (marks().some((mark) => mark.schedule_id === scheduleId)) conflict("Marks are already entered for this paper, so it can't be removed.");
    db().offlineSchedules = schedules().filter((item) => item.id !== scheduleId);
    save();
    await delay(null);
  },
  async schedules(query) {
    return delay(
      schedules()
        .filter((row) => !query.examId || row.exam_id === query.examId)
        .filter((row) => !query.sessionYearId || row.session_year_id === query.sessionYearId)
        .filter((row) => !query.classSectionId || row.class_section_id === query.classSectionId)
        .sort((a, b) => a.exam_date.localeCompare(b.exam_date) || (a.start_time ?? "").localeCompare(b.start_time ?? "")),
    );
  },
  async marks(scheduleId) {
    return delay(marks().filter((row) => row.schedule_id === scheduleId));
  },
  async saveMarks(exam, scheduleId, items) {
    const row = findExam(exam.id);
    const schedule = schedules().find((item) => item.id === scheduleId) ?? notFound("Exam paper");
    if (row.publish) throw new AcademicApiError(422, "Unpublish results before entering or correcting marks");
    const roster = new Map((await enrolled(schedule)).map((student) => [student.id, student]));
    const failures: SaveMarksOutcome["failures"] = [];
    let saved = 0;
    for (const item of items) {
      const problem = markProblem(item, schedule.max_marks) || (roster.has(item.student_id) ? "" : "Student is not enrolled in this class-section/session");
      const current = marks().find((mark) => mark.schedule_id === scheduleId && mark.student_id === item.student_id);
      const value = item.status === "present" ? item.marks_obtained : null;
      const changed = current && (current.marks_obtained !== value || current.status !== item.status);
      if (!problem && changed && row.results_processed_at && !item.reason?.trim()) {
        failures.push({ student_id: item.student_id, message: "reason is required to correct marks after results were processed" });
        continue;
      }
      if (problem) {
        failures.push({ student_id: item.student_id, message: problem });
        continue;
      }
      if (current) {
        if (changed) {
          if (item.reason?.trim()) {
            db().offlineAudits.push({
              id: nextId(db().offlineAudits),
              mark_id: current.id,
              previous_marks: current.marks_obtained,
              new_marks: value,
              previous_status: current.status,
              new_status: item.status,
              reason: item.reason.trim(),
              created_at: nowIso(),
            });
          }
          if (row.results_processed_at) row.results_processed_at = null;
          Object.assign(current, { marks_obtained: value, status: item.status });
        }
      } else {
        const student = roster.get(item.student_id);
        marks().push({
          id: nextId(marks()),
          exam_id: exam.id,
          schedule_id: scheduleId,
          student_id: item.student_id,
          student_name: student?.name ?? `Student #${item.student_id}`,
          admission_no: student?.admission_no ?? null,
          marks_obtained: value,
          status: item.status,
        });
      }
      saved += 1;
    }
    save();
    return delay({ saved, failures });
  },
  async audits(markId) {
    return delay(db().offlineAudits.filter((row) => row.mark_id === markId).sort((a, b) => b.id - a.id));
  },
  async processResults(examId) {
    const exam = findExam(examId);
    const papers = schedules().filter((item) => item.exam_id === examId);
    if (!papers.length) throw new AcademicApiError(422, "Exam has no subject schedules");
    const students = await enrolled(exam);
    let processed = 0;
    let pending = 0;
    const now = nowIso();
    for (const student of students) {
      const mine = papers.map((paper) => marks().find((mark) => mark.schedule_id === paper.id && mark.student_id === student.id));
      if (mine.some((mark) => !mark)) {
        pending += 1;
        continue;
      }
      let totalMax = 0;
      let totalObtained = 0;
      let passedAll = true;
      const subjects: ResultSubject[] = papers.map((paper, index) => {
        const mark = mine[index] as OfflineMark;
        if (mark.status === "withheld") {
          return { schedule_id: paper.id, subject_id: paper.subject_id, subject_name: paper.subject_name, status: mark.status, marks_obtained: null, max_marks: paper.max_marks, passed: null, included: false };
        }
        const obtained = mark.status === "absent" ? 0 : Number(mark.marks_obtained ?? 0);
        totalMax += paper.max_marks;
        totalObtained += obtained;
        const passed = obtained >= paper.passing_marks;
        if (!passed) passedAll = false;
        return { schedule_id: paper.id, subject_id: paper.subject_id, subject_name: paper.subject_name, status: mark.status, marks_obtained: obtained, max_marks: paper.max_marks, passing_marks: paper.passing_marks, passed, included: true };
      });
      const percentage = totalMax ? Math.round((totalObtained / totalMax) * 10000) / 100 : 0;
      const existing = results().find((row) => row.exam_id === examId && row.student_id === student.id);
      const value: OfflineResult = {
        id: existing?.id ?? nextId(results()),
        exam_id: examId,
        student_id: student.id,
        student_name: student.name,
        admission_no: student.admission_no,
        total_max_marks: totalMax,
        total_obtained: totalObtained,
        percentage,
        passed: passedAll && totalMax > 0,
        processed_at: now,
        subjects,
      };
      if (existing) Object.assign(existing, value);
      else results().push(value);
      processed += 1;
    }
    exam.results_processed_at = now;
    save();
    return delay({ processed_students: processed, pending_students: pending, enrolled_students: students.length });
  },
  async results(examId) {
    return delay(results().filter((row) => row.exam_id === examId).sort((a, b) => a.student_id - b.student_id));
  },
  async summary(examId) {
    const exam = findExam(examId);
    const students = await enrolled(exam);
    const list = results().filter((row) => row.exam_id === examId);
    const ids = new Set(list.map((row) => row.student_id));
    const passed = list.filter((row) => row.passed).length;
    return delay({
      publish: exam.publish,
      enrolled_students: students.length,
      processed_students: list.length,
      pending_students: students.filter((student) => !ids.has(student.id)).length,
      passed_count: passed,
      failed_count: list.length - passed,
    });
  },
};

/** Editing or removing a paper works only on sample data until the server has routes for it. */
export function paperEditing(): boolean {
  return !isLive("offline");
}

/** Every exam matching the filters (all pages), for sorting on the page. */
export async function allOfflineExams(query: OfflineExamQuery): Promise<OfflineExam[]> {
  const first = await offlineService().list({ ...query, page: 1, pageSize: 50 });
  const pages = Math.min(20, Math.ceil(first.total / 50));
  const rest = await Promise.all(Array.from({ length: Math.max(pages - 1, 0) }, (_, index) => offlineService().list({ ...query, page: index + 2, pageSize: 50 })));
  return [...first.items, ...rest.flatMap((page) => page.items)];
}

export function offlineService(): OfflineExamService {
  return isLive("offline") ? liveOffline : mockOffline;
}

/** Students who sit an exam: active students of its section in its session. */
export async function examRoster(exam: { session_year_id: number; class_section_id: number }) {
  return enrolled(exam);
}
