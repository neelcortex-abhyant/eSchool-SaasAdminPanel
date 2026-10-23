/**
 * Live academics client for the FastAPI School Admin routes.
 * The server derives the school from the Bearer session, so no request sends a school_id.
 *
 * The backend on main implements a smaller academics model than
 * backend/docs/ACADEMICS_API_CONTRACT.md describes. This client adapts to it:
 * - classes, sections and subjects have no status, and classes have no session, so rows
 *   come back active and in every session (see LIVE_ACADEMICS_LIMITS in lib/academics/index.ts);
 * - a section is added with POST /school-admin/sections {name, class_id} (find or create),
 *   and renamed by pointing the class section at another school section;
 * - a subject's classes are saved with PUT /school-admin/subjects/{id}/classes, without
 *   the compulsory or elective type;
 * - filters the server ignores (session status, search on sections and assignments,
 *   subject type) run here on the full list.
 */
import { api } from "@/lib/api";
import { AcademicApiError, errorFromResponse } from "@/lib/academics/errors";
import type {
  AcademicSession,
  AcademicsService,
  AssignmentInput,
  AssignmentQuery,
  ClassInput,
  ClassQuery,
  ClassSection,
  ListQuery,
  Medium,
  Page,
  RecordStatus,
  SchoolClass,
  SectionInput,
  SectionQuery,
  SessionInput,
  Subject,
  SubjectInput,
  SubjectKind,
  SubjectQuery,
  SubjectType,
  Teacher,
  TeacherAssignment,
} from "@/lib/academics/types";

/** Direct School Admin routes; the generic academics routes live under ACADEMICS. */
const BASE = "/school-admin";
const ACADEMICS = "/academics";
/** The backend caps page_size at 50. */
const LOOKUP_PAGE_SIZE = 50;
/** Client-side filters read at most this many pages (1,000 rows). */
const MAX_PAGES = 20;

type Raw = Record<string, unknown>;
type QueryValue = string | number | null | undefined;

async function request<T>(path: string, init: RequestInit, fallback: string): Promise<T> {
  let result;
  try {
    result = await api<T>(`${BASE}${path}`, init);
  } catch {
    throw errorFromResponse(0, null, fallback);
  }
  if (!result.ok) throw errorFromResponse(result.status, result.data, fallback);
  return result.data;
}

function get<T>(path: string, params: Record<string, QueryValue>, fallback: string) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const suffix = search.toString();
  return request<T>(suffix ? `${path}?${suffix}` : path, { method: "GET" }, fallback);
}

function send<T>(method: "POST" | "PATCH" | "PUT" | "DELETE", path: string, body: unknown, fallback: string) {
  return request<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) }, fallback);
}

function listParams(query: ListQuery = {}) {
  return {
    page: query.page ?? 1,
    page_size: Math.min(query.pageSize ?? 20, LOOKUP_PAGE_SIZE),
    q: query.q?.trim(),
  };
}

function str(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : value === null || value === undefined ? fallback : String(value);
}

function num(value: unknown): number {
  return typeof value === "number" ? value : Number(value ?? 0);
}

function status(value: unknown): RecordStatus {
  return value === 0 || value === "0" ? 0 : 1;
}

function matches(text: string, q?: string): boolean {
  const needle = q?.trim().toLowerCase();
  return !needle || text.toLowerCase().includes(needle);
}

function page<T>(data: Raw, map: (row: Raw) => T): Page<T> {
  const items = Array.isArray(data.items) ? (data.items as Raw[]) : [];
  return {
    items: items.map(map),
    total: num(data.total ?? items.length),
    page: num(data.page ?? 1),
    page_size: num(data.page_size ?? items.length),
  };
}

function slice<T>(rows: T[], pageNumber = 1, pageSize = 20): Page<T> {
  const size = Math.min(Math.max(pageSize, 1), LOOKUP_PAGE_SIZE);
  const current = Math.max(pageNumber, 1);
  return { items: rows.slice((current - 1) * size, current * size), total: rows.length, page: current, page_size: size };
}

/** Every row of a list, for filters the server doesn't apply. */
async function all(path: string, params: Record<string, QueryValue>, fallback: string): Promise<Raw[]> {
  const rows: Raw[] = [];
  for (let p = 1; p <= MAX_PAGES; p += 1) {
    const data = await get<Raw>(path, { ...params, page: p, page_size: LOOKUP_PAGE_SIZE }, fallback);
    const items = Array.isArray(data.items) ? (data.items as Raw[]) : [];
    rows.push(...items);
    if (items.length === 0 || rows.length >= num(data.total ?? rows.length)) break;
  }
  return rows;
}

// Medium names aren't in class or subject rows, so they're looked up once per page load.
let mediumNames: Promise<Map<number, string>> | null = null;

function mediumLookup(): Promise<Map<number, string>> {
  mediumNames ??= all(`${ACADEMICS}/mediums`, {}, "Unable to load mediums.")
    .then((rows) => new Map(rows.map((row) => [num(row.id), str(row.name)])))
    .catch((error) => {
      mediumNames = null;
      throw error;
    });
  return mediumNames;
}

function toSession(row: Raw): AcademicSession {
  return {
    id: num(row.id),
    name: str(row.name),
    start_date: str(row.start_date),
    end_date: str(row.end_date),
    is_active: row.is_active === true || num(row.default) === 1,
  };
}

function toClass(row: Raw, mediums?: Map<number, string>): SchoolClass {
  const sessionId = row.session_year_id === null || row.session_year_id === undefined ? null : num(row.session_year_id);
  const mediumId = num(row.medium_id);
  return {
    id: num(row.id),
    name: str(row.name),
    medium_id: mediumId,
    medium_name: str(row.medium_name, mediums?.get(mediumId) ?? `Medium #${mediumId}`),
    session_year_id: sessionId,
    session_name: sessionId === null ? "" : str(row.session_name, `Session #${sessionId}`),
    status: status(row.status),
  };
}

function toSection(row: Raw): ClassSection {
  return {
    id: num(row.id),
    class_id: num(row.class_id),
    class_name: str(row.class_name, `Class #${str(row.class_id)}`),
    section_id: num(row.section_id),
    section_name: str(row.section_name, `Section #${str(row.section_id)}`),
    status: status(row.status),
  };
}

function toSubject(row: Raw, mediums?: Map<number, string>, links?: Raw[]): Subject {
  const classes = links ?? (Array.isArray(row.classes) ? (row.classes as Raw[]) : []);
  const mediumId = num(row.medium_id);
  return {
    id: num(row.id),
    name: str(row.name),
    code: row.code ? str(row.code) : null,
    type: (str(row.type, "Theory") === "Practical" ? "Practical" : "Theory") as SubjectType,
    medium_id: mediumId,
    medium_name: str(row.medium_name, mediums?.get(mediumId) ?? `Medium #${mediumId}`),
    classes: classes.map((link) => ({
      class_id: num(link.class_id),
      class_name: str(link.class_name, `Class #${str(link.class_id)}`),
      type: (str(link.type) === "Elective" ? "Elective" : "Compulsory") as SubjectKind,
    })),
    status: status(row.status),
  };
}

function toAssignment(row: Raw): TeacherAssignment {
  return {
    id: num(row.id),
    session_year_id: num(row.session_year_id),
    session_name: str(row.session_name),
    class_id: num(row.class_id),
    class_name: str(row.class_name),
    class_section_id: num(row.class_section_id),
    section_name: str(row.section_name),
    subject_id: num(row.subject_id),
    subject_name: str(row.subject_name),
    teacher_id: num(row.teacher_id),
    teacher_name: str(row.teacher_name),
  };
}

function statusMatches(value: RecordStatus, filter?: string): boolean {
  return filter !== "0" && filter !== "1" ? true : String(value) === filter;
}

async function subjectClasses(subjectId: number): Promise<Raw[]> {
  return all(`/subjects/${subjectId}/classes`, {}, "Unable to load the subject's classes.");
}

async function subjectOut(row: Raw): Promise<Subject> {
  const [mediums, links] = await Promise.all([mediumLookup(), subjectClasses(num(row.id))]);
  return toSubject(row, mediums, links);
}

/** Saves a subject's classes after the subject itself; says so when only the first step worked. */
async function saveSubjectClasses(subject: Raw, input: SubjectInput, created: boolean): Promise<Subject> {
  try {
    await send<Raw>("PUT", `/subjects/${num(subject.id)}/classes`, { class_ids: input.classes.map((link) => link.class_id) }, "Unable to save the subject's classes.");
  } catch (error) {
    const reason = error instanceof AcademicApiError ? error.message : "Unable to save the subject's classes.";
    throw new AcademicApiError(
      error instanceof AcademicApiError ? error.status : 0,
      `${str(subject.name)} was ${created ? "added" : "saved"}, but its classes weren't saved: ${reason} Open the subject and save its classes again.`,
    );
  }
  return subjectOut(subject);
}

/** The school section with this name (any case), created when the school has none. */
async function sectionByName(name: string): Promise<number> {
  const wanted = name.trim();
  const rows = await all("/sections", { q: wanted }, "Unable to load sections.");
  const found = rows.find((row) => str(row.name).trim().toLowerCase() === wanted.toLowerCase());
  if (found) return num(found.id);
  const created = await send<Raw>("POST", `${ACADEMICS}/sections`, { name: wanted }, "Unable to add the section.");
  return num(created.id);
}

function classBody(input: ClassInput) {
  // The server stores only these fields; session and status aren't saved yet.
  return { name: input.name, medium_id: input.medium_id };
}

function subjectBody(input: SubjectInput) {
  return { name: input.name, code: input.code?.trim() || null, type: input.type, medium_id: input.medium_id };
}

export const httpAcademicsService: AcademicsService = {
  async listSessions(query) {
    if (query?.status === "0" || query?.status === "1") {
      // The server ignores status, so the active filter runs here.
      const rows = (await all(`${ACADEMICS}/sessions`, { q: query.q?.trim() }, "Unable to load academic sessions."))
        .map(toSession)
        .filter((row) => String(row.is_active ? 1 : 0) === query.status);
      return slice(rows, query.page, query.pageSize);
    }
    return page(await get<Raw>(`${ACADEMICS}/sessions`, listParams(query), "Unable to load academic sessions."), toSession);
  },
  async createSession(input: SessionInput) {
    return toSession(await send<Raw>("POST", `${ACADEMICS}/sessions`, input, "Unable to create the session."));
  },
  async updateSession(id, input) {
    return toSession(await send<Raw>("PATCH", `${ACADEMICS}/sessions/${id}`, input, "Unable to save the session."));
  },
  async activateSession(id) {
    return toSession(await send<Raw>("POST", `${ACADEMICS}/sessions/${id}/activate`, undefined, "Unable to activate the session."));
  },

  async listMediums(): Promise<Medium[]> {
    const data = await get<Raw>(`${ACADEMICS}/mediums`, { page: 1, page_size: LOOKUP_PAGE_SIZE }, "Unable to load mediums.");
    return page(data, (row) => ({ id: num(row.id), name: str(row.name) })).items;
  },
  async createMedium(name: string): Promise<Medium> {
    const row = await send<Raw>("POST", `${ACADEMICS}/mediums`, { name: name.trim() }, "Unable to add the medium.");
    mediumNames = null; // the next class or subject list picks up the new name
    return { id: num(row.id), name: str(row.name) };
  },
  async updateMedium(id, name) {
    const row = await send<Raw>("PATCH", `${ACADEMICS}/mediums/${id}`, { name: name.trim() }, "Unable to save the medium.");
    mediumNames = null;
    return { id: num(row.id ?? id), name: str(row.name, name.trim()) };
  },
  async deleteMedium(id) {
    await send<Raw>("DELETE", `${ACADEMICS}/mediums/${id}`, undefined, "Unable to delete the medium.");
    mediumNames = null;
  },

  async listClasses(query: ClassQuery = {}) {
    const [data, mediums] = await Promise.all([
      get<Raw>("/classes", { ...listParams(query), medium_id: query.mediumId }, "Unable to load classes."),
      mediumLookup(),
    ]);
    return page(data, (row) => toClass(row, mediums));
  },
  async createClass(input: ClassInput) {
    const [row, mediums] = await Promise.all([send<Raw>("POST", "/classes", classBody(input), "Unable to create the class."), mediumLookup()]);
    return toClass(row, mediums);
  },
  async updateClass(id, input) {
    const [row, mediums] = await Promise.all([send<Raw>("PATCH", `/classes/${id}`, classBody(input), "Unable to save the class."), mediumLookup()]);
    return toClass(row, mediums);
  },

  async listSections(query: SectionQuery = {}) {
    const params = { class_id: query.classId };
    if (query.q?.trim() || query.status === "0" || query.status === "1") {
      // The server doesn't search class sections, so search and status run here.
      const rows = (await all(`${ACADEMICS}/class-sections`, params, "Unable to load sections."))
        .map(toSection)
        .filter((row) => matches(`${row.class_name} ${row.section_name}`, query.q) && statusMatches(row.status, query.status));
      return slice(rows, query.page, query.pageSize);
    }
    return page(await get<Raw>(`${ACADEMICS}/class-sections`, { ...listParams(query), ...params }, "Unable to load sections."), toSection);
  },
  async createSection(input: SectionInput) {
    const row = await send<Raw>("POST", "/sections", { name: input.section_name, class_id: input.class_id }, "Unable to add the section.");
    // POST /sections answers with the school section plus the new class_section_id.
    return toSection({
      id: row.class_section_id,
      class_id: row.class_id,
      class_name: row.class_name,
      section_id: row.id,
      section_name: row.name,
    });
  },
  async updateSection(id, input) {
    const sectionId = await sectionByName(input.section_name);
    return toSection(await send<Raw>("PATCH", `${ACADEMICS}/class-sections/${id}`, { section_id: sectionId }, "Unable to save the section."));
  },

  async listSubjects(query: SubjectQuery = {}) {
    const params = { q: query.q?.trim(), class_id: query.classId };
    let rows: Raw[];
    let result: Page<Raw>;
    if (query.type || query.status === "0" || query.status === "1") {
      // The server doesn't filter by type or status, so those run here.
      rows = (await all("/subjects", params, "Unable to load subjects.")).filter(
        (row) => (!query.type || str(row.type, "Theory") === query.type) && statusMatches(status(row.status), query.status),
      );
      result = slice(rows, query.page, query.pageSize);
    } else {
      result = page(await get<Raw>("/subjects", { ...listParams(query), ...params }, "Unable to load subjects."), (row) => row);
    }
    return { ...result, items: await Promise.all(result.items.map(subjectOut)) };
  },
  async createSubject(input: SubjectInput) {
    const row = await send<Raw>("POST", "/subjects", subjectBody(input), "Unable to create the subject.");
    return saveSubjectClasses(row, input, true);
  },
  async updateSubject(id, input) {
    const row = await send<Raw>("PATCH", `/subjects/${id}`, subjectBody(input), "Unable to save the subject.");
    return saveSubjectClasses(row, input, false);
  },

  async listTeachers(q = ""): Promise<Teacher[]> {
    const params = { page: 1, page_size: LOOKUP_PAGE_SIZE, q: q.trim() };
    let data: Raw;
    try {
      // The people API lists teachers only. Before it's deployed, the academics lookup also
      // returns non-teaching staff, so fall back to it on 404.
      data = await get<Raw>("/teachers", { ...params, status: 1 }, "Unable to load teachers.");
    } catch (error) {
      if (!(error instanceof AcademicApiError) || error.status !== 404) throw error;
      data = await get<Raw>(`${ACADEMICS}/teachers`, params, "Unable to load teachers.");
    }
    return page(data, (row) => ({
      id: num(row.id),
      name: str(row.name) || `${str(row.first_name)} ${str(row.last_name)}`.trim(),
      email: str(row.email),
    })).items;
  },

  async listAssignments(query: AssignmentQuery = {}) {
    const params = {
      session_year_id: query.sessionYearId,
      class_id: query.classId,
      class_section_id: query.classSectionId,
      subject_id: query.subjectId,
      teacher_id: query.teacherId,
    };
    if (query.q?.trim()) {
      // The server doesn't search assignments, so search runs here.
      const rows = (await all(`${ACADEMICS}/teacher-assignments`, params, "Unable to load teacher assignments."))
        .map(toAssignment)
        .filter((row) => matches(`${row.teacher_name} ${row.subject_name} ${row.class_name} ${row.section_name}`, query.q));
      return slice(rows, query.page, query.pageSize);
    }
    return page(await get<Raw>(`${ACADEMICS}/teacher-assignments`, { ...listParams(query), ...params }, "Unable to load teacher assignments."), toAssignment);
  },
  async createAssignment(input: AssignmentInput) {
    return toAssignment(await send<Raw>("POST", `${ACADEMICS}/teacher-assignments`, input, "Unable to assign the teacher."));
  },
  async updateAssignment(id, input) {
    return toAssignment(await send<Raw>("PATCH", `${ACADEMICS}/teacher-assignments/${id}`, input, "Unable to save the assignment."));
  },
  async deleteAssignment(id) {
    await send<Raw>("DELETE", `${ACADEMICS}/teacher-assignments/${id}`, undefined, "Unable to remove the assignment.");
  },
};
