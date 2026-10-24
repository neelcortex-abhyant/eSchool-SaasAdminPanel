/**
 * Student attendance.
 * Live: the backend's generic /school-admin/academics/attendances route: list (page only) and
 * create one record at a time with type 1 present, 0 absent or 2 late. Rows carry only the
 * student id and date, so class and section come from the students list, and summaries are
 * worked out here. Bulk marking posts one record per student with limited concurrency.
 * The live backend has no Leave status, no correction (update) route and no lock routes, so
 * those are sample data only (attendanceSupport()).
 */
import { listAll } from "@/lib/academics";
import { peopleService, type StudentRow } from "@/lib/people";
import { allPages, notAvailable, num, optStr, send, settleLimited, str } from "@/lib/teaching/client";
import { isLive } from "@/lib/teaching/mode";
import { conflict, db, delay, invalid, nextId, notFound, nowIso, save } from "@/lib/teaching/store";
import type { AttendanceLock, AttendanceMark, AttendanceQuery, AttendanceRecord, AttendanceStatus } from "@/lib/teaching/types";

export type MarkResult = { student_id: number; ok: boolean; skipped?: boolean; message?: string };

export interface AttendanceService {
  records(query?: AttendanceQuery): Promise<AttendanceRecord[]>;
  mark(sessionYearId: number, classSectionId: number, date: string, marks: AttendanceMark[]): Promise<MarkResult[]>;
  correct(id: number, status: AttendanceStatus, remark: string | null): Promise<AttendanceRecord>;
  locks(classSectionId: number): Promise<AttendanceLock[]>;
  setLock(classSectionId: number, date: string, locked: boolean): Promise<void>;
}

export type AttendanceSupport = { leave: boolean; correction: boolean; locks: boolean };

export function attendanceSupport(): AttendanceSupport {
  return isLive("attendance") ? { leave: false, correction: false, locks: false } : { leave: true, correction: true, locks: true };
}

export const STATUS_LABEL: Record<AttendanceStatus, string> = { present: "Present", absent: "Absent", late: "Late", leave: "Leave" };

const LIVE_TYPE: Record<Exclude<AttendanceStatus, "leave">, number> = { present: 1, absent: 0, late: 2 };

function statusFromType(type: unknown): AttendanceStatus {
  const value = num(type);
  return value === 1 ? "present" : value === 2 ? "late" : "absent";
}

async function students(sessionYearId?: number | "", classSectionId?: number | ""): Promise<StudentRow[]> {
  return listAll((page) => peopleService("students").listStudents({ page, pageSize: 50, sessionYearId, classSectionId }));
}

function inRange(record: { date: string }, query: AttendanceQuery) {
  return (!query.from || record.date >= query.from) && (!query.to || record.date <= query.to);
}

export const liveAttendance: AttendanceService = {
  async records(query = {}) {
    const [rows, roster] = await Promise.all([
      allPages("/school-admin/academics/attendances", {}, "Unable to load attendance."),
      students(query.sessionYearId, query.classSectionId),
    ]);
    const byId = new Map(roster.map((student) => [student.id, student]));
    return rows
      .map((row): AttendanceRecord | null => {
        const student = byId.get(num(row.student_id));
        if (!student) return null;
        return {
          id: num(row.id),
          student_id: student.id,
          student_name: student.name,
          admission_no: student.admission_no,
          class_section_id: student.class_section_id,
          session_year_id: student.session_year_id,
          date: str(row.date).slice(0, 10),
          status: statusFromType(row.type),
          remark: optStr(row.remark),
          history: [],
        };
      })
      .filter((record): record is AttendanceRecord => record !== null)
      .filter((record) => (!query.studentId || record.student_id === query.studentId) && inRange(record, query));
  },
  async mark(sessionYearId, classSectionId, date, marks) {
    const existing = new Set((await liveAttendance.records({ sessionYearId, classSectionId, from: date, to: date })).map((record) => record.student_id));
    const tasks = marks.map((mark) => async (): Promise<MarkResult> => {
      if (existing.has(mark.student_id)) return { student_id: mark.student_id, ok: false, skipped: true, message: "Already marked for this date" };
      if (mark.status === "leave") return { student_id: mark.student_id, ok: false, message: "Leave isn't available on the server" };
      await send(
        "POST",
        "/school-admin/academics/attendances",
        { student_id: mark.student_id, class_section_id: classSectionId, session_year_id: sessionYearId, date, type: LIVE_TYPE[mark.status], remark: mark.remark?.trim() || null },
        "Unable to save attendance.",
      );
      return { student_id: mark.student_id, ok: true };
    });
    const settled = await settleLimited(tasks, 4);
    return settled.map((result, index) =>
      result.ok ? result.value : { student_id: marks[index].student_id, ok: false, message: (result.error as Error)?.message ?? "Failed" },
    );
  },
  async correct() {
    return notAvailable("Correcting attendance isn't available on the school's server yet.");
  },
  async locks() {
    return [];
  },
  async setLock() {
    return notAvailable("Locking attendance isn't available on the school's server yet.");
  },
};

// ---------- sample data ----------

function rows(): AttendanceRecord[] {
  return db().attendance as AttendanceRecord[];
}

function lockRows(): AttendanceLock[] {
  return db().locks as AttendanceLock[];
}

function isLocked(classSectionId: number, date: string) {
  return lockRows().some((lock) => lock.class_section_id === classSectionId && lock.date === date && lock.locked);
}

export const mockAttendance: AttendanceService = {
  async records(query = {}) {
    return delay(
      rows()
        .filter((row) => !query.sessionYearId || row.session_year_id === query.sessionYearId)
        .filter((row) => !query.classSectionId || row.class_section_id === query.classSectionId)
        .filter((row) => !query.studentId || row.student_id === query.studentId)
        .filter((row) => inRange(row, query)),
    );
  },
  async mark(sessionYearId, classSectionId, date, marks) {
    if (!date) invalid({ date: "Choose a date." });
    if (date > new Date().toISOString().slice(0, 10)) invalid({ date: "Attendance can't be marked for a future date." });
    if (isLocked(classSectionId, date)) conflict("Attendance for this section and date is locked. Unlock it before making changes.");
    const roster = new Map((await students(sessionYearId, classSectionId)).map((student) => [student.id, student]));
    const results: MarkResult[] = [];
    for (const mark of marks) {
      const student = roster.get(mark.student_id);
      const existing = rows().find((row) => row.student_id === mark.student_id && row.date === date);
      if (existing) {
        if (existing.status !== mark.status || (existing.remark ?? null) !== (mark.remark?.trim() || null)) {
          existing.history.unshift({ status: existing.status, remark: existing.remark, changed_at: nowIso() });
          existing.status = mark.status;
          existing.remark = mark.remark?.trim() || null;
        }
        results.push({ student_id: mark.student_id, ok: true });
        continue;
      }
      rows().push({
        id: nextId(rows()),
        student_id: mark.student_id,
        student_name: student?.name ?? `Student #${mark.student_id}`,
        admission_no: student?.admission_no ?? "",
        class_section_id: classSectionId,
        session_year_id: sessionYearId,
        date,
        status: mark.status,
        remark: mark.remark?.trim() || null,
        history: [],
      });
      results.push({ student_id: mark.student_id, ok: true });
    }
    save();
    return delay(results);
  },
  async correct(id, status, remark) {
    const row = rows().find((item) => item.id === id) ?? notFound("Attendance record");
    if (isLocked(row.class_section_id, row.date)) conflict("Attendance for this section and date is locked. Unlock it before making changes.");
    row.history.unshift({ status: row.status, remark: row.remark, changed_at: nowIso() });
    row.status = status;
    row.remark = remark?.trim() || null;
    save();
    return delay(row);
  },
  async locks(classSectionId) {
    return delay(lockRows().filter((lock) => lock.class_section_id === classSectionId));
  },
  async setLock(classSectionId, date, locked) {
    const existing = lockRows().find((lock) => lock.class_section_id === classSectionId && lock.date === date);
    if (existing) existing.locked = locked;
    else lockRows().push({ class_section_id: classSectionId, date, locked });
    save();
    await delay(null);
  },
};

export function attendanceService(): AttendanceService {
  return isLive("attendance") ? liveAttendance : mockAttendance;
}

/** Counts by status and the attendance percentage (present + late over all marked). */
export function tally(records: { status: AttendanceStatus }[]) {
  const counts: Record<AttendanceStatus, number> = { present: 0, absent: 0, late: 0, leave: 0 };
  for (const record of records) counts[record.status] += 1;
  const marked = records.length;
  const percent = marked ? Math.round(((counts.present + counts.late) / marked) * 1000) / 10 : 0;
  return { ...counts, marked, percent };
}

export { students as attendanceRoster };
