/**
 * Class timetable and teacher schedules.
 * Live: /school-admin/timetable-entries (list, create, get, PATCH, DELETE),
 *       /school-admin/timetable/weekly, /school-admin/teachers/{id}/timetable[/daily|/weekly],
 *       /school-admin/teachers/{id}/availability. Overlaps come back as 409 sentences.
 * The live backend has no classroom field; `room` is sample data only.
 */
import { allPages, get, hhmm, num, optStr, pageOf, send, str, type Raw } from "@/lib/teaching/client";
import { isLive } from "@/lib/teaching/mode";
import { placementOf, subjectName, teacherName } from "@/lib/teaching/lookups";
import { conflict, db, delay, invalid, nextId, notFound, paginate, save } from "@/lib/teaching/store";
import {
  WEEK_DAYS,
  type Availability,
  type Page,
  type TimetableEntry,
  type TimetableInput,
  type TimetableQuery,
  type WeekDay,
  type WeekGrid,
} from "@/lib/teaching/types";

export interface TimetableService {
  list(query?: TimetableQuery): Promise<Page<TimetableEntry>>;
  weekly(sessionYearId: number, classSectionId: number): Promise<WeekGrid>;
  create(input: TimetableInput): Promise<TimetableEntry>;
  update(id: number, input: TimetableInput): Promise<TimetableEntry>;
  remove(id: number): Promise<void>;
  teacherWeekly(teacherId: number, sessionYearId: number): Promise<WeekGrid>;
  availability(teacherId: number, check: { sessionYearId: number; day: WeekDay; start: string; end: string; excludeId?: number }): Promise<Availability>;
}

const BASE = "/school-admin";

function entryOf(row: Raw): TimetableEntry {
  return {
    id: num(row.id ?? row.entry_id),
    session_year_id: num(row.session_year_id),
    class_section_id: num(row.class_section_id),
    class_id: num(row.class_id),
    class_name: str(row.class_name),
    section_name: str(row.section_name),
    subject_id: num(row.subject_id),
    subject_name: str(row.subject_name),
    teacher_user_id: num(row.teacher_user_id),
    teacher_name: str(row.teacher_name),
    day: str(row.day, "monday") as WeekDay,
    start_time: hhmm(row.start_time),
    end_time: hhmm(row.end_time),
    note: optStr(row.note),
    room: null,
  };
}

function gridOf(data: Raw): WeekGrid {
  const days = Array.isArray(data.days) ? (data.days as Raw[]) : [];
  return WEEK_DAYS.map((day) => {
    const found = days.find((item) => str(item.day) === day);
    const entries = found && Array.isArray(found.entries) ? (found.entries as Raw[]).map(entryOf) : [];
    return { day, entries: entries.sort((a, b) => a.start_time.localeCompare(b.start_time)) };
  });
}

function body(input: TimetableInput) {
  return {
    session_year_id: input.session_year_id,
    class_section_id: input.class_section_id,
    subject_id: input.subject_id,
    teacher_user_id: input.teacher_user_id,
    day: input.day,
    start_time: input.start_time,
    end_time: input.end_time,
    note: input.note?.trim() || null,
  };
}

export const liveTimetable: TimetableService = {
  async list(query = {}) {
    const data = await get(`${BASE}/timetable-entries`, {
      page: query.page ?? 1,
      page_size: Math.min(query.pageSize ?? 20, 50),
      session_year_id: query.sessionYearId,
      class_id: query.classId,
      class_section_id: query.classSectionId,
      day: query.day,
    }, "Unable to load the timetable.");
    return pageOf(data, entryOf);
  },
  async weekly(sessionYearId, classSectionId) {
    return gridOf(await get(`${BASE}/timetable/weekly`, { session_year_id: sessionYearId, class_section_id: classSectionId }, "Unable to load the weekly timetable."));
  },
  async create(input) {
    return entryOf(await send("POST", `${BASE}/timetable-entries`, body(input), "Unable to add the period."));
  },
  async update(id, input) {
    return entryOf(await send("PATCH", `${BASE}/timetable-entries/${id}`, body(input), "Unable to save the period."));
  },
  async remove(id) {
    await send("DELETE", `${BASE}/timetable-entries/${id}`, undefined, "Unable to delete the period.");
  },
  async teacherWeekly(teacherId, sessionYearId) {
    return gridOf(await get(`${BASE}/teachers/${teacherId}/timetable/weekly`, { session_year_id: sessionYearId }, "Unable to load the teacher's schedule."));
  },
  async availability(teacherId, check) {
    const data = await get(`${BASE}/teachers/${teacherId}/availability`, {
      session_year_id: check.sessionYearId,
      day: check.day,
      start_time: check.start,
      end_time: check.end,
      exclude_entry_id: check.excludeId,
    }, "Unable to check availability.");
    const conflicts = Array.isArray(data.conflicts) ? (data.conflicts as Raw[]) : [];
    return { available: Boolean(data.available), conflicts: conflicts.map((row) => ({ ...entryOf(row), id: num(row.entry_id) })) };
  },
};

// ---------- sample data ----------

type Row = TimetableEntry;

function rows(): Row[] {
  return db().timetable as Row[];
}

function overlaps(a: { start_time: string; end_time: string }, b: { start_time: string; end_time: string }) {
  return a.start_time < b.end_time && b.start_time < a.end_time;
}

function check(input: TimetableInput, ignoreId?: number) {
  const errors: Record<string, string> = {};
  if (!input.session_year_id) errors.session_year_id = "Choose an academic session.";
  if (!input.class_section_id) errors.class_section_id = "Choose a section.";
  if (!input.subject_id) errors.subject_id = "Choose a subject.";
  if (!input.teacher_user_id) errors.teacher_user_id = "Choose a teacher.";
  if (!(WEEK_DAYS as readonly string[]).includes(input.day)) errors.day = "Choose a day.";
  if (!/^\d{2}:\d{2}$/.test(input.start_time)) errors.start_time = "Enter a start time.";
  if (!/^\d{2}:\d{2}$/.test(input.end_time)) errors.end_time = "Enter an end time.";
  else if (input.end_time <= input.start_time) errors.end_time = "End time must be after the start time.";
  if (Object.keys(errors).length) invalid(errors);
  const sameDay = rows().filter((row) => row.id !== ignoreId && row.session_year_id === input.session_year_id && row.day === input.day);
  if (sameDay.some((row) => row.class_section_id === input.class_section_id && overlaps(row, input))) {
    conflict("Timetable period overlaps an existing class period");
  }
  if (sameDay.some((row) => row.teacher_user_id === input.teacher_user_id && overlaps(row, input))) {
    conflict("Teacher is already scheduled for an overlapping period");
  }
}

async function build(input: TimetableInput, id: number): Promise<Row> {
  const [placement, subject, teacher] = await Promise.all([
    placementOf(input.session_year_id, input.class_section_id),
    subjectName(input.subject_id),
    teacherName(input.teacher_user_id),
  ]);
  return {
    id,
    ...placement,
    subject_id: input.subject_id,
    subject_name: subject,
    teacher_user_id: input.teacher_user_id,
    teacher_name: teacher,
    day: input.day,
    start_time: input.start_time,
    end_time: input.end_time,
    note: input.note?.trim() || null,
    room: input.room?.trim() || null,
  };
}

function grid(list: Row[]): WeekGrid {
  return WEEK_DAYS.map((day) => ({ day, entries: list.filter((row) => row.day === day).sort((a, b) => a.start_time.localeCompare(b.start_time)) }));
}

export const mockTimetable: TimetableService = {
  async list(query = {}) {
    const list = rows()
      .filter((row) => !query.sessionYearId || row.session_year_id === query.sessionYearId)
      .filter((row) => !query.classId || row.class_id === query.classId)
      .filter((row) => !query.classSectionId || row.class_section_id === query.classSectionId)
      .filter((row) => !query.day || row.day === query.day)
      .sort((a, b) => WEEK_DAYS.indexOf(a.day) - WEEK_DAYS.indexOf(b.day) || a.start_time.localeCompare(b.start_time) || a.id - b.id);
    return delay(paginate(list, query.page, query.pageSize));
  },
  async weekly(sessionYearId, classSectionId) {
    return delay(grid(rows().filter((row) => row.session_year_id === sessionYearId && row.class_section_id === classSectionId)));
  },
  async create(input) {
    check(input);
    const row = await build(input, nextId(rows()));
    rows().push(row);
    save();
    return delay(row);
  },
  async update(id, input) {
    const index = rows().findIndex((row) => row.id === id);
    if (index < 0) notFound("Timetable period");
    check(input, id);
    const row = await build(input, id);
    rows()[index] = row;
    save();
    return delay(row);
  },
  async remove(id) {
    const index = rows().findIndex((row) => row.id === id);
    if (index < 0) notFound("Timetable period");
    rows().splice(index, 1);
    save();
    await delay(null);
  },
  async teacherWeekly(teacherId, sessionYearId) {
    return delay(grid(rows().filter((row) => row.teacher_user_id === teacherId && row.session_year_id === sessionYearId)));
  },
  async availability(teacherId, checkInput) {
    const conflicts = rows().filter(
      (row) =>
        row.id !== checkInput.excludeId &&
        row.teacher_user_id === teacherId &&
        row.session_year_id === checkInput.sessionYearId &&
        row.day === checkInput.day &&
        overlaps(row, { start_time: checkInput.start, end_time: checkInput.end }),
    );
    return delay({ available: conflicts.length === 0, conflicts });
  },
};

export function timetableService(): TimetableService {
  return isLive("timetable") ? liveTimetable : mockTimetable;
}

/** Every entry for a section in a session, for pickers and summaries. */
export async function allEntries(sessionYearId: number, classSectionId: number): Promise<TimetableEntry[]> {
  if (!isLive("timetable")) return (await mockTimetable.list({ sessionYearId, classSectionId, pageSize: 50 })).items;
  return (await allPages(`${BASE}/timetable-entries`, { session_year_id: sessionYearId, class_section_id: classSectionId }, "Unable to load the timetable.")).map(entryOf);
}
