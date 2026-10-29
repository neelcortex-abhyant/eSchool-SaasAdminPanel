/**
 * Mock academics client. It follows the same contract and validation rules as the live API
 * (backend/docs/ACADEMICS_API_CONTRACT.md) so pages behave the same before and after the switch.
 * Data starts from mock-data.json and is kept in this browser's localStorage.
 */
import seed from "@/lib/academics/mock-data.json";
import { AcademicApiError } from "@/lib/academics/errors";
import type {
  AcademicSession,
  AcademicsService,
  AssignmentInput,
  ClassInput,
  ClassSection,
  Page,
  RecordStatus,
  SchoolClass,
  SectionInput,
  SessionInput,
  Subject,
  SubjectInput,
  SubjectKind,
  SubjectType,
  TeacherAssignment,
} from "@/lib/academics/types";

type Db = {
  sessions: { id: number; name: string; start_date: string; end_date: string; default: number }[];
  mediums: { id: number; name: string }[];
  classes: { id: number; name: string; medium_id: number; session_year_id: number | null; status: number }[];
  sections: { id: number; name: string }[];
  class_sections: { id: number; class_id: number; section_id: number; status: number }[];
  subjects: { id: number; name: string; code: string | null; type: string; medium_id: number; status: number }[];
  class_subjects: { class_id: number; subject_id: number; type: string }[];
  teachers: { id: number; name: string; email: string }[];
  teacher_assignments: { id: number; session_year_id: number; class_section_id: number; subject_id: number; teacher_id: number }[];
};

const STORAGE_KEY = "academics-mock-db-v1";
const LATENCY_MS = 0;

let memory: Db | null = null;

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function db(): Db {
  if (memory) return memory;
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) memory = JSON.parse(saved) as Db;
  } catch {
    memory = null;
  }
  memory ??= clone(seed as Db);
  return memory;
}

function save(): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(memory));
  } catch {
    // Storage can be unavailable (private mode). The in-memory copy still works for this tab.
  }
}

/** Clears local changes and restores mock-data.json. */
export function resetMockAcademics(): void {
  memory = clone(seed as Db);
  save();
}

/** A copy of the mock academic records, so the people mock can show class and session names. */
export function mockAcademicSnapshot(): Pick<Db, "sessions" | "classes" | "sections" | "class_sections"> {
  return clone(db());
}

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => window.setTimeout(() => resolve(clone(value)), LATENCY_MS));
}

function nextId(rows: { id: number }[]): number {
  return rows.reduce((max, row) => Math.max(max, row.id), 0) + 1;
}

function invalid(field: string, message: string): never {
  throw new AcademicApiError(422, "Check the highlighted fields.", { [field]: message });
}

function conflict(message: string): never {
  throw new AcademicApiError(409, message);
}

function notFound(label = "Record"): never {
  throw new AcademicApiError(404, `${label} not found`);
}

function same(a: string, b: string): boolean {
  return a.trim().toLowerCase() === b.trim().toLowerCase();
}

function matches(text: string, q?: string): boolean {
  const needle = q?.trim().toLowerCase();
  return !needle || text.toLowerCase().includes(needle);
}

function paginate<T>(rows: T[], pageNumber = 1, pageSize = 20): Page<T> {
  const size = Math.min(Math.max(pageSize, 1), 50);
  const lastPage = Math.max(1, Math.ceil(rows.length / size));
  const current = Math.min(Math.max(pageNumber, 1), lastPage);
  return { items: rows.slice((current - 1) * size, current * size), total: rows.length, page: current, page_size: size };
}

function statusMatches(status: number, filter?: string): boolean {
  return filter !== "0" && filter !== "1" ? true : String(status) === filter;
}

function requireName(value: string, field = "name", label = "Name"): string {
  const name = (value || "").trim();
  if (!name) invalid(field, `${label} is required`);
  if (name.length > 255) invalid(field, `${label} must be 255 characters or fewer`);
  return name;
}

function asStatus(value: number): RecordStatus {
  return value === 0 ? 0 : 1;
}

// ---------- read models ----------

function sessionOut(row: Db["sessions"][number]): AcademicSession {
  return { id: row.id, name: row.name, start_date: row.start_date, end_date: row.end_date, is_active: row.default === 1 };
}

function classOut(row: Db["classes"][number]): SchoolClass {
  const data = db();
  const medium = data.mediums.find((m) => m.id === row.medium_id);
  const session = data.sessions.find((s) => s.id === row.session_year_id);
  return {
    id: row.id,
    name: row.name,
    medium_id: row.medium_id,
    medium_name: medium?.name ?? "",
    session_year_id: row.session_year_id,
    session_name: session?.name ?? "",
    status: asStatus(row.status),
  };
}

function sectionOut(row: Db["class_sections"][number]): ClassSection {
  const data = db();
  const schoolClass = data.classes.find((c) => c.id === row.class_id);
  const medium = data.mediums.find((m) => m.id === schoolClass?.medium_id);
  const section = data.sections.find((s) => s.id === row.section_id);
  return {
    id: row.id,
    class_id: row.class_id,
    class_name: schoolClass ? classLabel(schoolClass.name, medium?.name) : "",
    section_id: row.section_id,
    section_name: section?.name ?? "",
    status: asStatus(row.status),
  };
}

/** Classes with the same name can exist in two mediums, so labels carry the medium when it helps. */
function classLabel(name: string, medium?: string): string {
  const data = db();
  const duplicates = data.classes.filter((c) => same(c.name, name)).length;
  return duplicates > 1 && medium ? `${name} (${medium})` : name;
}

function subjectOut(row: Db["subjects"][number]): Subject {
  const data = db();
  const medium = data.mediums.find((m) => m.id === row.medium_id);
  return {
    id: row.id,
    name: row.name,
    code: row.code,
    type: (row.type === "Practical" ? "Practical" : "Theory") as SubjectType,
    medium_id: row.medium_id,
    medium_name: medium?.name ?? "",
    classes: data.class_subjects
      .filter((link) => link.subject_id === row.id)
      .map((link) => {
        const schoolClass = data.classes.find((c) => c.id === link.class_id);
        const classMedium = data.mediums.find((m) => m.id === schoolClass?.medium_id);
        return {
          class_id: link.class_id,
          class_name: schoolClass ? classLabel(schoolClass.name, classMedium?.name) : "",
          type: (link.type === "Elective" ? "Elective" : "Compulsory") as SubjectKind,
        };
      }),
    status: asStatus(row.status),
  };
}

function assignmentOut(row: Db["teacher_assignments"][number]): TeacherAssignment {
  const data = db();
  const section = data.class_sections.find((cs) => cs.id === row.class_section_id);
  const view = section ? sectionOut(section) : null;
  return {
    id: row.id,
    session_year_id: row.session_year_id,
    session_name: data.sessions.find((s) => s.id === row.session_year_id)?.name ?? "",
    class_id: view?.class_id ?? 0,
    class_name: view?.class_name ?? "",
    class_section_id: row.class_section_id,
    section_name: view?.section_name ?? "",
    subject_id: row.subject_id,
    subject_name: data.subjects.find((s) => s.id === row.subject_id)?.name ?? "",
    teacher_id: row.teacher_id,
    teacher_name: data.teachers.find((t) => t.id === row.teacher_id)?.name ?? "",
  };
}

// ---------- validation ----------

function validateSession(input: SessionInput, ignoreId?: number) {
  const data = db();
  const name = requireName(input.name);
  if (!input.start_date) invalid("start_date", "Start date is required");
  if (!input.end_date) invalid("end_date", "End date is required");
  if (input.end_date <= input.start_date) invalid("end_date", "End date must be after the start date");
  if (data.sessions.some((s) => s.id !== ignoreId && same(s.name, name))) conflict(`A session named ${name} already exists`);
  const overlap = data.sessions.find((s) => s.id !== ignoreId && s.start_date <= input.end_date && input.start_date <= s.end_date);
  if (overlap) conflict(`These dates overlap the ${overlap.name} session`);
  return { name, start_date: input.start_date, end_date: input.end_date };
}

function validateClass(input: ClassInput, ignoreId?: number) {
  const data = db();
  const name = requireName(input.name, "name", "Class name");
  if (!data.mediums.some((m) => m.id === input.medium_id)) invalid("medium_id", "Choose a medium");
  if (input.session_year_id !== null && !data.sessions.some((s) => s.id === input.session_year_id)) {
    invalid("session_year_id", "Session does not belong to this school");
  }
  if (data.classes.some((c) => c.id !== ignoreId && c.medium_id === input.medium_id && same(c.name, name))) {
    conflict(`${name} already exists in this medium`);
  }
  return { name, medium_id: input.medium_id, session_year_id: input.session_year_id, status: asStatus(input.status) };
}

function validateSection(input: SectionInput, ignoreId?: number) {
  const data = db();
  const schoolClass = data.classes.find((c) => c.id === input.class_id);
  if (!schoolClass) invalid("class_id", "Choose a class");
  const name = requireName(input.section_name, "section_name", "Section name");
  if (name.length > 32) invalid("section_name", "Section name must be 32 characters or fewer");
  let section = data.sections.find((s) => same(s.name, name));
  const duplicate = section && data.class_sections.some((cs) => cs.id !== ignoreId && cs.class_id === input.class_id && cs.section_id === section!.id);
  if (duplicate) conflict(`Section ${name} already exists in ${schoolClass.name}`);
  if (!section) {
    section = { id: nextId(data.sections), name };
    data.sections.push(section);
  }
  return { class_id: input.class_id, section_id: section.id, status: asStatus(input.status) };
}

function validateSubject(input: SubjectInput, ignoreId?: number) {
  const data = db();
  const name = requireName(input.name, "name", "Subject name");
  const code = (input.code || "").trim().toUpperCase() || null;
  if (code && code.length > 64) invalid("code", "Code must be 64 characters or fewer");
  if (input.type !== "Theory" && input.type !== "Practical") invalid("type", "Choose Theory or Practical");
  if (!data.mediums.some((m) => m.id === input.medium_id)) invalid("medium_id", "Choose a medium");
  if (code && data.subjects.some((s) => s.id !== ignoreId && s.code && same(s.code, code))) conflict(`Subject code ${code} is already in use`);
  if (data.subjects.some((s) => s.id !== ignoreId && s.medium_id === input.medium_id && same(s.name, name) && (s.type === input.type))) {
    conflict(`${name} (${input.type}) already exists in this medium`);
  }
  const seen = new Set<number>();
  for (const link of input.classes) {
    const schoolClass = data.classes.find((c) => c.id === link.class_id);
    if (!schoolClass) invalid("classes", "A selected class does not belong to this school");
    if (schoolClass.medium_id !== input.medium_id) invalid("classes", `${schoolClass.name} uses a different medium`);
    if (seen.has(link.class_id)) invalid("classes", `${schoolClass.name} is selected twice`);
    if (link.type !== "Compulsory" && link.type !== "Elective") invalid("classes", "Choose compulsory or elective");
    seen.add(link.class_id);
  }
  return { name, code, type: input.type, medium_id: input.medium_id, status: asStatus(input.status) };
}

function validateAssignment(input: AssignmentInput, ignoreId?: number) {
  const data = db();
  const session = data.sessions.find((s) => s.id === input.session_year_id);
  if (!session) invalid("session_year_id", "Choose an academic session");
  const section = data.class_sections.find((cs) => cs.id === input.class_section_id);
  if (!section) invalid("class_section_id", "Choose a section");
  if (section.status !== 1) invalid("class_section_id", "This section is inactive");
  const schoolClass = data.classes.find((c) => c.id === section.class_id);
  if (!schoolClass || schoolClass.status !== 1) invalid("class_section_id", "This class is inactive");
  if (schoolClass.session_year_id !== null && schoolClass.session_year_id !== session.id) {
    invalid("class_section_id", `${schoolClass.name} is not part of the ${session.name} session`);
  }
  const subject = data.subjects.find((s) => s.id === input.subject_id);
  if (!subject) invalid("subject_id", "Choose a subject");
  if (subject.status !== 1) invalid("subject_id", "This subject is inactive");
  if (!data.class_subjects.some((link) => link.class_id === schoolClass.id && link.subject_id === subject.id)) {
    invalid("subject_id", `${subject.name} is not taught in ${schoolClass.name}`);
  }
  const teacher = data.teachers.find((t) => t.id === input.teacher_id);
  if (!teacher) invalid("teacher_id", "Choose a teacher");
  const taken = data.teacher_assignments.find(
    (a) => a.id !== ignoreId && a.session_year_id === session.id && a.class_section_id === section.id && a.subject_id === subject.id,
  );
  if (taken) {
    const holder = data.teachers.find((t) => t.id === taken.teacher_id)?.name ?? "another teacher";
    const sectionName = data.sections.find((s) => s.id === section.section_id)?.name ?? "";
    conflict(`${subject.name} in ${schoolClass.name} ${sectionName} is already assigned to ${holder} for ${session.name}`);
  }
  return { ...input };
}

// ---------- service ----------

export const mockAcademicsService: AcademicsService = {
  async listSessions(query = {}) {
    const rows = db()
      .sessions.filter((s) => matches(s.name, query.q))
      .filter((s) => statusMatches(s.default === 1 ? 1 : 0, query.status))
      .sort((a, b) => b.start_date.localeCompare(a.start_date))
      .map(sessionOut);
    return delay(paginate(rows, query.page, query.pageSize));
  },
  async createSession(input) {
    const data = db();
    const clean = validateSession(input);
    const row = { id: nextId(data.sessions), ...clean, default: data.sessions.length === 0 ? 1 : 0 };
    data.sessions.push(row);
    save();
    return delay(sessionOut(row));
  },
  async updateSession(id, input) {
    const row = db().sessions.find((s) => s.id === id) ?? notFound("Session");
    Object.assign(row, validateSession(input, id));
    save();
    return delay(sessionOut(row));
  },
  async activateSession(id) {
    const data = db();
    const row = data.sessions.find((s) => s.id === id) ?? notFound("Session");
    data.sessions.forEach((s) => {
      s.default = s.id === row.id ? 1 : 0;
    });
    save();
    return delay(sessionOut(row));
  },

  async listMediums() {
    return delay(db().mediums);
  },
  async createMedium(name) {
    const data = db();
    const clean = requireName(name, "name", "Medium name");
    if (data.mediums.some((m) => same(m.name, clean))) conflict(`A medium named ${clean} already exists`);
    const row = { id: nextId(data.mediums), name: clean };
    data.mediums.push(row);
    save();
    return delay(row);
  },
  async updateMedium(id, name) {
    const data = db();
    const row = data.mediums.find((m) => m.id === id) ?? notFound("Medium");
    const clean = requireName(name, "name", "Medium name");
    if (data.mediums.some((m) => m.id !== id && same(m.name, clean))) conflict(`A medium named ${clean} already exists`);
    row.name = clean;
    save();
    return delay(row);
  },
  async deleteMedium(id) {
    const data = db();
    const row = data.mediums.find((m) => m.id === id) ?? notFound("Medium");
    const used = data.classes.filter((c) => c.medium_id === id).length + data.subjects.filter((s) => s.medium_id === id).length;
    if (used) conflict(`${row.name} is used by classes or subjects. Move or delete them first.`);
    data.mediums = data.mediums.filter((m) => m.id !== id);
    save();
    await delay(null);
  },

  async listClasses(query = {}) {
    const rows = db()
      .classes.filter((c) => matches(c.name, query.q))
      .filter((c) => statusMatches(c.status, query.status))
      .filter((c) => !query.mediumId || c.medium_id === query.mediumId)
      // A class with no session is offered in every session.
      .filter((c) => !query.sessionYearId || c.session_year_id === null || c.session_year_id === query.sessionYearId)
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }) || a.medium_id - b.medium_id)
      .map(classOut);
    return delay(paginate(rows, query.page, query.pageSize));
  },
  async createClass(input) {
    const data = db();
    const row = { id: nextId(data.classes), ...validateClass(input) };
    data.classes.push(row);
    save();
    return delay(classOut(row));
  },
  async updateClass(id, input) {
    const row = db().classes.find((c) => c.id === id) ?? notFound("Class");
    Object.assign(row, validateClass(input, id));
    save();
    return delay(classOut(row));
  },

  async listSections(query = {}) {
    const rows = db()
      .class_sections.filter((cs) => !query.classId || cs.class_id === query.classId)
      .filter((cs) => statusMatches(cs.status, query.status))
      .map(sectionOut)
      .filter((cs) => matches(`${cs.class_name} ${cs.section_name}`, query.q))
      .sort((a, b) => a.class_name.localeCompare(b.class_name, undefined, { numeric: true }) || a.section_name.localeCompare(b.section_name));
    return delay(paginate(rows, query.page, query.pageSize));
  },
  async createSection(input) {
    const data = db();
    const row = { id: nextId(data.class_sections), ...validateSection(input) };
    data.class_sections.push(row);
    save();
    return delay(sectionOut(row));
  },
  async updateSection(id, input) {
    const row = db().class_sections.find((cs) => cs.id === id) ?? notFound("Section");
    Object.assign(row, validateSection(input, id));
    save();
    return delay(sectionOut(row));
  },

  async listSubjects(query = {}) {
    const rows = db()
      .subjects.filter((s) => matches(`${s.name} ${s.code ?? ""}`, query.q))
      .filter((s) => statusMatches(s.status, query.status))
      .filter((s) => !query.type || s.type === query.type)
      .map(subjectOut)
      .filter((s) => !query.classId || s.classes.some((link) => link.class_id === query.classId && (!query.kind || link.type === query.kind)))
      .filter((s) => !query.kind || query.classId || s.classes.some((link) => link.type === query.kind))
      .sort((a, b) => a.name.localeCompare(b.name));
    return delay(paginate(rows, query.page, query.pageSize));
  },
  async createSubject(input) {
    const data = db();
    const row = { id: nextId(data.subjects), ...validateSubject(input) };
    data.subjects.push(row);
    data.class_subjects.push(...input.classes.map((link) => ({ class_id: link.class_id, subject_id: row.id, type: link.type })));
    save();
    return delay(subjectOut(row));
  },
  async updateSubject(id, input) {
    const data = db();
    const row = data.subjects.find((s) => s.id === id) ?? notFound("Subject");
    const clean = validateSubject(input, id);
    const kept = new Set(input.classes.map((link) => link.class_id));
    const assigned = data.teacher_assignments.find((a) => {
      if (a.subject_id !== id) return false;
      const section = data.class_sections.find((cs) => cs.id === a.class_section_id);
      return section ? !kept.has(section.class_id) : false;
    });
    if (assigned) {
      const section = data.class_sections.find((cs) => cs.id === assigned.class_section_id);
      const className = data.classes.find((c) => c.id === section?.class_id)?.name ?? "a class";
      conflict(`Remove the teacher assignments for ${row.name} in ${className} before unmapping it`);
    }
    Object.assign(row, clean);
    data.class_subjects = data.class_subjects.filter((link) => link.subject_id !== id);
    data.class_subjects.push(...input.classes.map((link) => ({ class_id: link.class_id, subject_id: id, type: link.type })));
    save();
    return delay(subjectOut(row));
  },

  async listTeachers(q = "") {
    return delay(db().teachers.filter((t) => matches(`${t.name} ${t.email}`, q)));
  },

  async listAssignments(query = {}) {
    const rows = db()
      .teacher_assignments.map(assignmentOut)
      .filter((a) => !query.sessionYearId || a.session_year_id === query.sessionYearId)
      .filter((a) => !query.classId || a.class_id === query.classId)
      .filter((a) => !query.classSectionId || a.class_section_id === query.classSectionId)
      .filter((a) => !query.subjectId || a.subject_id === query.subjectId)
      .filter((a) => !query.teacherId || a.teacher_id === query.teacherId)
      .filter((a) => matches(`${a.teacher_name} ${a.subject_name} ${a.class_name} ${a.section_name}`, query.q))
      .sort(
        (a, b) =>
          a.class_name.localeCompare(b.class_name, undefined, { numeric: true }) ||
          a.section_name.localeCompare(b.section_name) ||
          a.subject_name.localeCompare(b.subject_name),
      );
    return delay(paginate(rows, query.page, query.pageSize));
  },
  async createAssignment(input) {
    const data = db();
    const row = { id: nextId(data.teacher_assignments), ...validateAssignment(input) };
    data.teacher_assignments.push(row);
    save();
    return delay(assignmentOut(row));
  },
  async updateAssignment(id, input) {
    const row = db().teacher_assignments.find((a) => a.id === id) ?? notFound("Assignment");
    Object.assign(row, validateAssignment(input, id));
    save();
    return delay(assignmentOut(row));
  },
  async deleteAssignment(id) {
    const data = db();
    if (!data.teacher_assignments.some((a) => a.id === id)) notFound("Assignment");
    data.teacher_assignments = data.teacher_assignments.filter((a) => a.id !== id);
    save();
    await delay(null);
  },
};
