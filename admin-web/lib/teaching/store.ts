/**
 * Sample-data store for the teaching modules. Data starts from mock-data.json and is kept in
 * this browser's localStorage, like the academics and people mocks. Session, class, section,
 * subject, teacher and student ids match those mocks so dropdowns and records line up.
 */
import seed from "@/lib/teaching/mock-data.json";
import { AcademicApiError } from "@/lib/academics/errors";
import type {
  AttemptDetail,
  AttendanceLock,
  AttendanceRecord,
  BankQuestion,
  Homework,
  Material,
  OnlineExam,
  Page,
  Question,
  Submission,
  TimetableEntry,
} from "@/lib/teaching/types";
import type { OfflineAudit, OfflineExamRow, OfflineMark, OfflineResult, OfflineSchedule } from "@/lib/teaching/offlineTypes";

const STORAGE_KEY = "teaching-mock-db-v1";

type Db = {
  timetable: TimetableEntry[];
  homework: Homework[];
  submissions: Submission[];
  materials: Material[];
  exams: (OnlineExam & { questions: Question[] })[];
  attempts: (AttemptDetail & { exam_id: number })[];
  bank: BankQuestion[];
  attendance: AttendanceRecord[];
  locks: AttendanceLock[];
  offlineExams: OfflineExamRow[];
  offlineSchedules: OfflineSchedule[];
  offlineMarks: OfflineMark[];
  offlineAudits: OfflineAudit[];
  offlineResults: OfflineResult[];
};
const SEED = seed as unknown as Db;
let memory: Db | null = null;

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

export function db(): Db {
  if (memory) return memory;
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) memory = JSON.parse(saved) as Db;
    // Copies saved before a module was added lack its tables; start those from the seed.
    if (memory) for (const key of Object.keys(SEED) as (keyof Db)[]) if (!memory[key]) (memory as Record<string, unknown>)[key] = clone(SEED[key]);
  } catch {
    memory = null;
  }
  memory ??= clone(SEED);
  return memory;
}

export function save(): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(memory));
  } catch {
    // Storage can be full or unavailable (private mode). The in-memory copy still works for this tab.
  }
}

/** Clears local changes and restores mock-data.json. */
export function resetMockTeaching(): void {
  memory = clone(SEED);
  save();
}

export function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => window.setTimeout(() => resolve(clone(value)), 0));
}

export function nextId(rows: { id: number }[]): number {
  return rows.reduce((max, row) => Math.max(max, row.id), 0) + 1;
}

export function invalid(errors: Record<string, string>): never {
  throw new AcademicApiError(422, "Check the highlighted fields.", errors);
}

export function conflict(message: string): never {
  throw new AcademicApiError(409, message);
}

export function notFound(label: string): never {
  throw new AcademicApiError(404, `${label} not found`);
}

export function matches(q: string | undefined, ...values: (string | null | undefined)[]): boolean {
  const needle = (q ?? "").trim().toLowerCase();
  return !needle || values.some((value) => (value ?? "").toLowerCase().includes(needle));
}

export function paginate<T>(rows: T[], pageNumber = 1, pageSize = 20): Page<T> {
  const size = Math.min(Math.max(pageSize, 1), 50);
  const current = Math.max(pageNumber, 1);
  return { items: rows.slice((current - 1) * size, current * size), total: rows.length, page: current, page_size: size };
}

export function nowIso(): string {
  return new Date().toISOString();
}
