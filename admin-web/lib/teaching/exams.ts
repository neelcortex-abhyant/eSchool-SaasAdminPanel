/**
 * Online exams (multiple choice).
 * Live: /school-admin/online-assessments (list, create, get with questions and correct answers,
 * PATCH incl. status draft|published|closed and results_published, DELETE),
 * /online-assessments/{id}/questions (add), /questions/import (up to 100),
 * /online-assessment-questions/{id} (PATCH, DELETE), /online-assessments/{id}/attempts and
 * /online-assessment-attempts/{id}. Publishing is validated by the server (questions exist,
 * marks add up to total_marks, each question has exactly one correct choice); its 422
 * sentences are shown as is. Correct answers only come back on these admin routes.
 * The question bank shared across exams is sample data only.
 */
import { AcademicApiError } from "@/lib/academics/errors";
import { allPages, get, num, optNum, optStr, pageOf, send, settleLimited, str, type Raw } from "@/lib/teaching/client";
import { isLive } from "@/lib/teaching/mode";
import { placementOf, sectionMap, subjectName } from "@/lib/teaching/lookups";
import { conflict, db, delay, invalid, matches, nextId, notFound, paginate, save } from "@/lib/teaching/store";
import type {
  Attempt,
  AttemptDetail,
  AttemptStatus,
  BankQuestion,
  ExamDetail,
  ExamStatus,
  OnlineExam,
  OnlineExamInput,
  OnlineExamQuery,
  Page,
  Placement,
  Question,
  QuestionInput,
} from "@/lib/teaching/types";

export interface ExamService {
  list(query?: OnlineExamQuery): Promise<Page<OnlineExam>>;
  get(id: number): Promise<ExamDetail>;
  create(input: OnlineExamInput): Promise<OnlineExam>;
  update(id: number, input: OnlineExamInput): Promise<OnlineExam>;
  setStatus(id: number, status: ExamStatus): Promise<OnlineExam>;
  setResultsPublished(id: number, published: boolean): Promise<OnlineExam>;
  remove(id: number): Promise<void>;
  addQuestion(examId: number, input: QuestionInput): Promise<void>;
  updateQuestion(examId: number, questionId: number, input: QuestionInput): Promise<void>;
  removeQuestion(examId: number, questionId: number): Promise<void>;
  importQuestions(examId: number, items: QuestionInput[]): Promise<number>;
  attempts(examId: number): Promise<Attempt[]>;
  attempt(attemptId: number): Promise<AttemptDetail>;
}

const BASE = "/school-admin";

/** Checks one question before it's sent; the server repeats these rules. */
export function questionProblems(input: QuestionInput): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!input.question_text.trim()) errors.question_text = "Enter the question.";
  if (!(input.marks > 0)) errors.marks = "Marks must be more than 0.";
  const choices = input.choices.filter((choice) => choice.choice_text.trim());
  if (choices.length < 2 || choices.length > 8) errors.choices = "Add 2 to 8 answer choices.";
  else if (choices.filter((choice) => choice.is_correct).length !== 1) errors.choices = "Mark exactly one choice as correct.";
  return errors;
}

function examOf(row: Raw, sections: Map<number, Placement>): OnlineExam {
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
    title: str(row.title),
    instructions: optStr(row.instructions),
    duration_minutes: num(row.duration_minutes),
    total_marks: num(row.total_marks),
    passing_marks: num(row.passing_marks),
    available_from: str(row.available_from),
    available_until: str(row.available_until),
    status: str(row.status, "draft") as ExamStatus,
    results_published: Boolean(row.results_published),
  };
}

function questionOf(row: Raw): Question {
  const choices = Array.isArray(row.choices) ? (row.choices as Raw[]) : [];
  return {
    id: num(row.id),
    question_text: str(row.question_text),
    topic: optStr(row.topic),
    marks: num(row.marks),
    sort_order: num(row.sort_order),
    choices: choices.map((choice) => ({ id: num(choice.id), choice_text: str(choice.choice_text), is_correct: Boolean(choice.is_correct) })),
  };
}

function attemptOf(row: Raw): Attempt {
  return {
    id: num(row.id),
    student_id: num(row.student_id),
    student_name: str(row.student_name),
    admission_no: str(row.admission_no),
    status: str(row.status, "submitted") as AttemptStatus,
    started_at: optStr(row.started_at),
    submitted_at: optStr(row.submitted_at),
    score: optNum(row.score),
    percentage: optNum(row.percentage),
    passed: row.passed === null || row.passed === undefined ? null : Boolean(row.passed),
  };
}

function examBody(input: OnlineExamInput) {
  return {
    session_year_id: input.session_year_id,
    class_section_id: input.class_section_id,
    subject_id: input.subject_id,
    teacher_user_id: input.teacher_user_id,
    title: input.title.trim(),
    instructions: input.instructions?.trim() || null,
    duration_minutes: input.duration_minutes,
    total_marks: input.total_marks,
    passing_marks: input.passing_marks,
    available_from: input.available_from,
    available_until: input.available_until,
  };
}

function questionBody(input: QuestionInput) {
  return {
    question_text: input.question_text.trim(),
    marks: input.marks,
    topic: input.topic?.trim() || null,
    sort_order: input.sort_order,
    choices: input.choices.filter((choice) => choice.choice_text.trim()).map((choice) => ({ choice_text: choice.choice_text.trim(), is_correct: choice.is_correct })),
  };
}

export const liveExams: ExamService = {
  async list(query = {}) {
    const [data, sections] = await Promise.all([
      get(`${BASE}/online-assessments`, {
        page: query.page ?? 1,
        page_size: Math.min(query.pageSize ?? 20, 50),
        q: query.q?.trim(),
        session_year_id: query.sessionYearId,
        class_section_id: query.classSectionId,
        subject_id: query.subjectId,
        status: query.status,
      }, "Unable to load online exams."),
      sectionMap(),
    ]);
    return pageOf(data, (row) => examOf(row, sections));
  },
  async get(id) {
    const [row, sections] = await Promise.all([get(`${BASE}/online-assessments/${id}`, {}, "Unable to load this exam."), sectionMap()]);
    const exam = examOf(row, sections);
    const attemptCount = num(row.attempt_count);
    const questions = (Array.isArray(row.questions) ? (row.questions as Raw[]) : []).map(questionOf).sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
    return { ...exam, questions, attempt_count: attemptCount, locked: attemptCount > 0 && exam.status !== "draft" };
  },
  async create(input) {
    const [row, sections] = await Promise.all([send("POST", `${BASE}/online-assessments`, examBody(input), "Unable to create the exam."), sectionMap()]);
    return examOf(row, sections);
  },
  async update(id, input) {
    const [row, sections] = await Promise.all([send("PATCH", `${BASE}/online-assessments/${id}`, examBody(input), "Unable to save the exam."), sectionMap()]);
    return examOf(row, sections);
  },
  async setStatus(id, status) {
    const [row, sections] = await Promise.all([send("PATCH", `${BASE}/online-assessments/${id}`, { status }, "Unable to change the exam status."), sectionMap()]);
    return examOf(row, sections);
  },
  async setResultsPublished(id, published) {
    const [row, sections] = await Promise.all([send("PATCH", `${BASE}/online-assessments/${id}`, { results_published: published }, "Unable to change the results setting."), sectionMap()]);
    return examOf(row, sections);
  },
  async remove(id) {
    await send("DELETE", `${BASE}/online-assessments/${id}`, undefined, "Unable to delete the exam.");
  },
  async addQuestion(examId, input) {
    await send("POST", `${BASE}/online-assessments/${examId}/questions`, questionBody(input), "Unable to add the question.");
  },
  async updateQuestion(_examId, questionId, input) {
    await send("PATCH", `${BASE}/online-assessment-questions/${questionId}`, questionBody(input), "Unable to save the question.");
  },
  async removeQuestion(_examId, questionId) {
    await send("DELETE", `${BASE}/online-assessment-questions/${questionId}`, undefined, "Unable to delete the question.");
  },
  async importQuestions(examId, items) {
    const data = await send("POST", `${BASE}/online-assessments/${examId}/questions/import`, { items: items.map(questionBody) }, "Unable to import the questions.");
    return num(data.imported ?? data.count ?? items.length);
  },
  async attempts(examId) {
    return (await allPages(`${BASE}/online-assessments/${examId}/attempts`, {}, "Unable to load attempts.")).map(attemptOf);
  },
  async attempt(attemptId) {
    const row = await get(`${BASE}/online-assessment-attempts/${attemptId}`, {}, "Unable to load this attempt.");
    const questions = (Array.isArray(row.questions) ? (row.questions as Raw[]) : []).map(questionOf);
    const answers = Array.isArray(row.answers) ? (row.answers as Raw[]) : [];
    return {
      ...attemptOf(row),
      answers: questions.map((question) => {
        const answer = answers.find((item) => num(item.question_id) === question.id);
        return {
          question_text: question.question_text,
          marks: question.marks,
          chosen: question.choices.find((choice) => choice.id === num(answer?.choice_id))?.choice_text ?? null,
          correct: question.choices.find((choice) => choice.is_correct)?.choice_text ?? null,
          awarded: answer ? optNum(answer.marks_awarded) : null,
        };
      }),
    };
  },
};

// ---------- sample data ----------

type ExamRow = OnlineExam & { questions: Question[] };
type AttemptRow = AttemptDetail & { exam_id: number };

function examRows(): ExamRow[] {
  return db().exams as ExamRow[];
}

function attemptRows(): AttemptRow[] {
  return db().attempts as AttemptRow[];
}

function findExam(id: number): ExamRow {
  return examRows().find((row) => row.id === id) ?? notFound("Online exam");
}

function lockedExam(exam: ExamRow): boolean {
  return exam.status !== "draft" && attemptRows().some((row) => row.exam_id === exam.id);
}

function checkExam(input: OnlineExamInput) {
  const errors: Record<string, string> = {};
  if (!input.session_year_id) errors.session_year_id = "Choose an academic session.";
  if (!input.class_section_id) errors.class_section_id = "Choose a section.";
  if (!input.subject_id) errors.subject_id = "Choose a subject.";
  if (!input.teacher_user_id) errors.teacher_user_id = "Choose a teacher.";
  if (!input.title.trim()) errors.title = "Enter the exam name.";
  if (!(input.duration_minutes > 0)) errors.duration_minutes = "Duration must be at least 1 minute.";
  if (!(input.total_marks > 0)) errors.total_marks = "Total marks must be more than 0.";
  if (!(input.passing_marks >= 0) || input.passing_marks > input.total_marks) errors.passing_marks = "Passing marks must be between 0 and the total marks.";
  if (!input.available_from) errors.available_from = "Choose when the exam opens.";
  if (!input.available_until) errors.available_until = "Choose when the exam closes.";
  else if (input.available_from && input.available_until <= input.available_from) errors.available_until = "The exam must close after it opens.";
  if (Object.keys(errors).length) invalid(errors);
}

function assertEditable(exam: ExamRow) {
  if (lockedExam(exam)) conflict("Students have attempted this exam, so its questions can't change.");
}

async function buildExam(input: OnlineExamInput, base: Pick<ExamRow, "id" | "status" | "results_published" | "questions">): Promise<ExamRow> {
  const [placement, subject] = await Promise.all([placementOf(input.session_year_id, input.class_section_id), subjectName(input.subject_id)]);
  return { ...base, ...placement, ...examBody(input), subject_name: subject };
}

function nextQuestionId(): number {
  const ids = examRows().flatMap((exam) => exam.questions.map((q) => q.id)).concat((db().bank as BankQuestion[]).map((q) => q.id));
  return Math.max(0, ...ids) + 1;
}

export const mockExams: ExamService = {
  async list(query = {}) {
    const list = examRows()
      .filter((row) => !query.sessionYearId || row.session_year_id === query.sessionYearId)
      .filter((row) => !query.classSectionId || row.class_section_id === query.classSectionId)
      .filter((row) => !query.subjectId || row.subject_id === query.subjectId)
      .filter((row) => !query.status || row.status === query.status)
      .filter((row) => matches(query.q, row.title, row.subject_name))
      .sort((a, b) => b.available_from.localeCompare(a.available_from))
      .map(({ questions: _questions, ...exam }) => exam);
    return delay(paginate(list, query.page, query.pageSize));
  },
  async get(id) {
    const exam = findExam(id);
    return delay({ ...exam, questions: [...exam.questions].sort((a, b) => a.sort_order - b.sort_order), attempt_count: attemptRows().filter((row) => row.exam_id === id).length, locked: lockedExam(exam) });
  },
  async create(input) {
    checkExam(input);
    const row = await buildExam(input, { id: nextId(examRows()), status: "draft", results_published: false, questions: [] });
    examRows().push(row);
    save();
    const { questions: _q, ...exam } = row;
    return delay(exam);
  },
  async update(id, input) {
    const index = examRows().findIndex((row) => row.id === id);
    if (index < 0) notFound("Online exam");
    checkExam(input);
    const current = examRows()[index];
    if (lockedExam(current)) conflict("Students have attempted this exam, so it can't be edited.");
    const row = await buildExam(input, current);
    examRows()[index] = row;
    save();
    const { questions: _q, ...exam } = row;
    return delay(exam);
  },
  async setStatus(id, status) {
    const exam = findExam(id);
    if (status === "published") {
      // Same sentences the server sends as a 422 detail.
      if (exam.questions.length === 0) throw new AcademicApiError(422, "Cannot publish an assessment with no questions");
      const sum = exam.questions.reduce((total, q) => total + q.marks, 0);
      if (Math.abs(sum - exam.total_marks) > 0.001) throw new AcademicApiError(422, `Sum of question marks (${sum}) must equal total_marks (${exam.total_marks})`);
    }
    exam.status = status;
    save();
    const { questions: _q, ...rest } = exam;
    return delay(rest);
  },
  async setResultsPublished(id, published) {
    const exam = findExam(id);
    exam.results_published = published;
    save();
    const { questions: _q, ...rest } = exam;
    return delay(rest);
  },
  async remove(id) {
    findExam(id);
    db().exams = examRows().filter((row) => row.id !== id);
    db().attempts = attemptRows().filter((row) => row.exam_id !== id);
    save();
    await delay(null);
  },
  async addQuestion(examId, input) {
    const exam = findExam(examId);
    assertEditable(exam);
    const errors = questionProblems(input);
    if (Object.keys(errors).length) invalid(errors);
    const id = nextQuestionId();
    exam.questions.push({ ...input, id, choices: input.choices.filter((c) => c.choice_text.trim()).map((c, i) => ({ ...c, id: id * 10 + i })) });
    save();
  },
  async updateQuestion(examId, questionId, input) {
    const exam = findExam(examId);
    assertEditable(exam);
    const errors = questionProblems(input);
    if (Object.keys(errors).length) invalid(errors);
    const index = exam.questions.findIndex((q) => q.id === questionId);
    if (index < 0) notFound("Question");
    exam.questions[index] = { ...input, id: questionId, choices: input.choices.filter((c) => c.choice_text.trim()).map((c, i) => ({ ...c, id: questionId * 10 + i })) };
    save();
  },
  async removeQuestion(examId, questionId) {
    const exam = findExam(examId);
    assertEditable(exam);
    exam.questions = exam.questions.filter((q) => q.id !== questionId);
    save();
  },
  async importQuestions(examId, items) {
    if (items.length === 0 || items.length > 100) invalid({ import: "Import between 1 and 100 questions at a time." });
    items.forEach((item, index) => {
      const errors = questionProblems(item);
      if (Object.keys(errors).length) invalid({ import: `Question ${index + 1}: ${Object.values(errors)[0]}` });
    });
    for (const item of items) await mockExams.addQuestion(examId, item);
    return items.length;
  },
  async attempts(examId) {
    return delay(attemptRows().filter((row) => row.exam_id === examId).map(({ answers: _a, exam_id: _e, ...attempt }) => attempt));
  },
  async attempt(attemptId) {
    const row = attemptRows().find((item) => item.id === attemptId) ?? notFound("Attempt");
    const { exam_id: _e, ...detail } = row;
    return delay(detail);
  },
};

export function examService(): ExamService {
  return isLive("exams") ? liveExams : mockExams;
}

// ---------- question bank (sample data in both modes) ----------

export function bankQuestions(q = "", subject = ""): BankQuestion[] {
  return (db().bank as BankQuestion[]).filter((row) => matches(q, row.question_text, row.topic) && (!subject || row.subject_name === subject));
}

export function saveBankQuestion(input: QuestionInput & { subject_name: string | null }, id?: number): BankQuestion {
  const errors = questionProblems(input);
  if (Object.keys(errors).length) invalid(errors);
  const bank = db().bank as BankQuestion[];
  const questionId = id ?? nextQuestionId();
  const row: BankQuestion = { ...input, id: questionId, choices: input.choices.filter((c) => c.choice_text.trim()).map((c, i) => ({ ...c, id: questionId * 10 + i })) };
  const index = bank.findIndex((item) => item.id === id);
  if (index >= 0) bank[index] = row;
  else bank.push(row);
  save();
  return row;
}

export function removeBankQuestion(id: number): void {
  db().bank = (db().bank as BankQuestion[]).filter((row) => row.id !== id);
  save();
}

/** Copies bank questions into an exam through the exam client (live or sample). Returns failures. */
export async function copyBankQuestionsToExam(examId: number, questions: BankQuestion[]): Promise<string[]> {
  const service = examService();
  const results = await settleLimited(
    questions.map((question, index) => () =>
      service.addQuestion(examId, { question_text: question.question_text, topic: question.topic, marks: question.marks, sort_order: 1000 + index, choices: question.choices.map((c) => ({ choice_text: c.choice_text, is_correct: c.is_correct })) }),
    ),
    2,
  );
  return results.flatMap((result, index) => (result.ok ? [] : [`${questions[index].question_text.slice(0, 40)}: ${(result.error as Error)?.message ?? "failed"}`]));
}
