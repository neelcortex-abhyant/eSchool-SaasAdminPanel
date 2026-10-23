/**
 * Live people client for the backend's generic School Admin routes:
 *   /school-admin/academics/students   list (page, q), create, PATCH (incl. status)
 *   /school-admin/academics/parents    list (page, q), create
 *   /school-admin/academics/teachers   list (page, q), create
 * The server derives the school from the Bearer session, so no request sends a school_id.
 *
 * These routes have no detail, filter or sort parameters, so this client reads the full list
 * (at most 1,000 rows) and filters, sorts and finds records here. Session, class and section
 * names come from the academics routes. Anything the routes can't store throws a clear error;
 * the pages hide those controls (peopleSupport in lib/people/index.ts).
 */
import { api } from "@/lib/api";
import { AcademicApiError, errorFromResponse } from "@/lib/academics/errors";
import type {
  ChildLink,
  Employee,
  EmployeeKind,
  EmployeeQuery,
  EmployeeRow,
  EmploymentType,
  Gender,
  GuardianLink,
  Page,
  Parent,
  ParentCreateInput,
  ParentQuery,
  PeopleService,
  RecordStatus,
  Student,
  StudentCreateInput,
  StudentInput,
  StudentQuery,
  StudentRow,
} from "@/lib/people/types";

const BASE = "/school-admin/academics";
/** The backend caps page_size at 50. */
const PAGE_SIZE = 50;
const MAX_PAGES = 20;

type Raw = Record<string, unknown>;

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

function send<T>(method: "POST" | "PATCH", path: string, body: unknown, fallback: string) {
  return request<T>(path, { method, body: JSON.stringify(body) }, fallback);
}

/** Every row of a list. */
async function all(resource: string, fallback: string, q = ""): Promise<Raw[]> {
  const rows: Raw[] = [];
  for (let page = 1; page <= MAX_PAGES; page += 1) {
    const search = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (q.trim()) search.set("q", q.trim());
    const data = await request<Raw>(`/${resource}?${search}`, { method: "GET" }, fallback);
    const items = Array.isArray(data.items) ? (data.items as Raw[]) : [];
    rows.push(...items);
    if (items.length === 0 || rows.length >= Number(data.total ?? rows.length)) break;
  }
  return rows;
}

function unsupported(message: string): never {
  throw new AcademicApiError(501, message);
}

function str(value: unknown): string {
  return typeof value === "string" ? value : value === null || value === undefined ? "" : String(value);
}

function num(value: unknown): number {
  return typeof value === "number" ? value : Number(value ?? 0);
}

function status(value: unknown): RecordStatus {
  return value === 0 || value === "0" ? 0 : 1;
}

function fullName(row: Raw): string {
  return str(row.name) || `${str(row.first_name)} ${str(row.last_name)}`.trim();
}

function digits(value: string | null | undefined): string {
  return (value ?? "").replace(/\D/g, "");
}

function matches(q: string | undefined, ...values: (string | null | undefined)[]): boolean {
  const needle = (q ?? "").trim().toLowerCase();
  return !needle || values.some((value) => (value ?? "").toLowerCase().includes(needle));
}

function slice<T>(rows: T[], pageNumber = 1, pageSize = 20): Page<T> {
  const size = Math.min(Math.max(pageSize, 1), PAGE_SIZE);
  const current = Math.max(pageNumber, 1);
  return { items: rows.slice((current - 1) * size, current * size), total: rows.length, page: current, page_size: size };
}

function statusMatches(value: RecordStatus, filter?: string): boolean {
  return filter !== "0" && filter !== "1" ? true : String(value) === filter;
}

// ---------- lookups ----------

type Placement = { class_id: number; class_name: string; section_name: string };

type Lookups = {
  sessions: Map<number, string>;
  sections: Map<number, Placement>;
  parents: Map<number, Raw>;
};

async function lookups(withParents: boolean): Promise<Lookups> {
  const [sessions, sections, parents] = await Promise.all([
    all("sessions", "Unable to load academic sessions."),
    all("class-sections", "Unable to load sections."),
    withParents ? all("parents", "Unable to load parents.") : Promise.resolve([] as Raw[]),
  ]);
  return {
    sessions: new Map(sessions.map((row) => [num(row.id), str(row.name)])),
    sections: new Map(
      sections.map((row) => [num(row.id), { class_id: num(row.class_id), class_name: str(row.class_name), section_name: str(row.section_name) }]),
    ),
    parents: new Map(parents.map((row) => [num(row.id), row])),
  };
}

// ---------- students ----------

function studentRow(row: Raw, look: Lookups): StudentRow {
  const placement = look.sections.get(num(row.class_section_id));
  const guardian = look.parents.get(num(row.guardian_id));
  return {
    id: num(row.id),
    admission_no: str(row.admission_no),
    first_name: str(row.first_name),
    last_name: str(row.last_name),
    name: fullName(row),
    session_year_id: num(row.session_year_id),
    session_name: look.sessions.get(num(row.session_year_id)) ?? "",
    class_id: placement?.class_id ?? 0,
    class_name: placement?.class_name ?? "",
    class_section_id: num(row.class_section_id),
    section_name: placement?.section_name ?? "",
    roll_number: row.roll_number === null || row.roll_number === undefined ? null : num(row.roll_number),
    guardian_name: str(row.guardian_name) || (guardian ? fullName(guardian) : null),
    guardian_mobile: guardian ? str(guardian.mobile) || null : null,
    admission_date: str(row.admission_date),
    photo_url: null,
    status: status(row.status),
  };
}

function studentDetail(row: Raw, look: Lookups): Student {
  const base = studentRow(row, look);
  const guardian = look.parents.get(num(row.guardian_id));
  const email = str(row.email);
  const guardians: GuardianLink[] = row.guardian_id
    ? [
        {
          parent_id: num(row.guardian_id),
          name: guardian ? fullName(guardian) : str(row.guardian_name),
          email: guardian ? str(guardian.email) || null : null,
          mobile: guardian ? str(guardian.mobile) || null : null,
          relationship: "Guardian",
          is_primary: true,
        },
      ]
    : [];
  return {
    ...base,
    // The server doesn't store these yet.
    dob: "",
    gender: "" as Gender,
    email: email.includes("@") ? email : null,
    mobile: null,
    current_address: "",
    permanent_address: null,
    guardians,
    documents: [],
  };
}

const STUDENT_SORTS: Record<string, (row: StudentRow) => string> = {
  name: (row) => row.name.toLowerCase(),
  admission_no: (row) => row.admission_no,
  admission_date: (row) => row.admission_date,
  class: (row) => `${row.class_name.padStart(12, " ")} ${row.section_name}`,
};

async function findStudent(id: number, look?: Lookups): Promise<Student> {
  const [rows, lk] = await Promise.all([all("students", "Unable to load this student."), look ? Promise.resolve(look) : lookups(true)]);
  const row = rows.find((item) => num(item.id) === id);
  if (!row) throw new AcademicApiError(404, "Student not found");
  return studentDetail(row, lk);
}

function nextAdmissionNo(rows: Raw[], admissionDate: string): string {
  const prefix = `ADM${admissionDate.slice(0, 4)}`;
  const used = rows.map((row) => str(row.admission_no)).filter((no) => no.startsWith(prefix)).map((no) => Number(no.slice(prefix.length)) || 0);
  return `${prefix}${String(Math.max(0, ...used) + 1).padStart(4, "0")}`;
}

function studentPatch(input: StudentInput) {
  return {
    first_name: input.first_name,
    last_name: input.last_name,
    admission_no: input.admission_no,
    roll_number: input.roll_number ?? null,
    admission_date: input.admission_date,
    class_section_id: input.class_section_id,
    session_year_id: input.session_year_id,
    status: input.status,
  };
}

// ---------- parents ----------

function childLinks(parentId: number, students: Raw[], look: Lookups): ChildLink[] {
  return students
    .filter((row) => num(row.guardian_id) === parentId)
    .map((row) => {
      const view = studentRow(row, look);
      return {
        student_id: view.id,
        name: view.name,
        admission_no: view.admission_no,
        class_name: view.class_name,
        section_name: view.section_name,
        relationship: "Guardian" as const,
        is_primary: true,
        status: view.status,
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name));
}

function parentOut(row: Raw, children: ChildLink[]): Parent {
  return {
    id: num(row.id),
    first_name: str(row.first_name),
    last_name: str(row.last_name),
    name: fullName(row),
    email: str(row.email),
    mobile: str(row.mobile),
    current_address: null,
    occupation: null,
    status: status(row.status),
    children,
  };
}

async function parentsWithChildren(): Promise<{ parents: Raw[]; students: Raw[]; look: Lookups }> {
  const [parents, students, look] = await Promise.all([
    all("parents", "Unable to load parents."),
    all("students", "Unable to load students."),
    lookups(false),
  ]);
  return { parents, students, look };
}

// ---------- teachers ----------

function employeeRow(row: Raw): EmployeeRow {
  return {
    id: num(row.id),
    employee_code: "",
    first_name: str(row.first_name),
    last_name: str(row.last_name),
    name: fullName(row),
    email: str(row.email),
    mobile: str(row.mobile),
    department: "",
    designation: "",
    joining_date: "",
    employment_type: "" as EmploymentType,
    photo_url: null,
    status: status(row.status),
  };
}

function employeeDetail(row: Raw): Employee {
  return { ...employeeRow(row), gender: null, dob: null, qualification: str(row.qualification) || null, current_address: null, documents: [] };
}

function teachersOnly(kind: EmployeeKind) {
  if (kind === "staff") unsupported("Staff isn't available on the school's server yet.");
}

const NO_FILES = "Photos and documents can't be uploaded to the school's server yet.";

export const httpPeopleService: PeopleService = {
  async listStudents(query: StudentQuery = {}) {
    const [rows, look] = await Promise.all([all("students", "Unable to load students.", query.q ?? ""), lookups(true)]);
    let views = rows
      .map((row) => ({ row, view: studentRow(row, look) }))
      .filter(({ view }) => statusMatches(view.status, query.status))
      .filter(({ view }) => !query.sessionYearId || view.session_year_id === query.sessionYearId)
      .filter(({ view }) => !query.classId || view.class_id === query.classId)
      .filter(({ view }) => !query.classSectionId || view.class_section_id === query.classSectionId)
      .filter(({ row }) => !query.parentId || num(row.guardian_id) === query.parentId)
      .map(({ view }) => view);
    const key = STUDENT_SORTS[query.sort ?? "name"] ?? STUDENT_SORTS.name;
    const order = query.order === "desc" ? -1 : 1;
    views = views.sort((a, b) => key(a).localeCompare(key(b), undefined, { numeric: true }) * order || a.id - b.id);
    return slice(views, query.page, query.pageSize);
  },

  async getStudent(id) {
    return findStudent(id);
  },

  async createStudent(input: StudentCreateInput) {
    if (!input.email) {
      throw new AcademicApiError(422, "Check the highlighted fields.", { email: "The school's server needs an email address for every student." });
    }
    const [rows, look] = await Promise.all([all("students", "Unable to load students."), lookups(true)]);
    let guardianId: number;
    if ("parent_id" in input.guardian) {
      guardianId = Number(input.guardian.parent_id);
    } else {
      const g = input.guardian;
      const parent = await send<Raw>("POST", "/parents", { first_name: g.first_name, last_name: g.last_name, email: g.email, mobile: g.mobile }, "Unable to add the parent.");
      guardianId = num(parent.id);
    }
    const created = await send<Raw>(
      "POST",
      "/students",
      {
        first_name: input.first_name,
        last_name: input.last_name,
        email: input.email,
        admission_no: input.admission_no || nextAdmissionNo(rows, input.admission_date),
        roll_number: input.roll_number ?? null,
        admission_date: input.admission_date,
        class_section_id: input.class_section_id,
        session_year_id: input.session_year_id,
        guardian_id: guardianId,
      },
      "Unable to admit the student.",
    );
    // New students start active on the server.
    const saved = input.status === 0 ? await send<Raw>("PATCH", `/students/${num(created.id)}`, { status: 0 }, "Unable to save the student's status.") : created;
    return findStudent(num(saved.id), look);
  },

  async updateStudent(id, input: StudentInput) {
    const saved = await send<Raw>("PATCH", `/students/${id}`, studentPatch(input), "Unable to save the student.");
    return studentDetail(saved, await lookups(true));
  },

  async setStudentStatus(id, value: RecordStatus) {
    const saved = await send<Raw>("PATCH", `/students/${id}`, { status: value }, "Unable to change the student's status.");
    return studentDetail(saved, await lookups(true));
  },

  async linkGuardian(studentId, link) {
    // The server keeps one guardian per student, so linking replaces the current one.
    const saved = await send<Raw>("PATCH", `/students/${studentId}`, { guardian_id: link.parent_id }, "Unable to link the guardian.");
    return studentDetail(saved, await lookups(true));
  },

  async unlinkGuardian() {
    return unsupported("The school's server keeps one guardian per student, so a guardian can't be removed.");
  },

  async listParents(query: ParentQuery = {}) {
    const { parents, students, look } = await parentsWithChildren();
    const rows = parents
      .map((row) => parentOut(row, childLinks(num(row.id), students, look)))
      .filter((row) => statusMatches(row.status, query.status))
      .filter((row) => !query.email?.trim() || row.email.toLowerCase() === query.email.trim().toLowerCase())
      .filter((row) => !digits(query.mobile) || digits(row.mobile) === digits(query.mobile))
      .filter((row) => matches(query.q, row.name, row.email, row.mobile))
      .sort((a, b) => a.name.localeCompare(b.name));
    return slice(rows, query.page, query.pageSize);
  },

  async getParent(id) {
    const { parents, students, look } = await parentsWithChildren();
    const row = parents.find((item) => num(item.id) === id);
    if (!row) throw new AcademicApiError(404, "Parent not found");
    return parentOut(row, childLinks(id, students, look));
  },

  async createParent(input: ParentCreateInput) {
    const created = await send<Raw>("POST", "/parents", { first_name: input.first_name, last_name: input.last_name, email: input.email, mobile: input.mobile }, "Unable to add the parent.");
    const id = num(created.id);
    // Linking a student makes this parent their guardian, replacing the current one.
    for (const link of input.students ?? []) {
      await send<Raw>("PATCH", `/students/${link.student_id}`, { guardian_id: id }, "Unable to link a student.");
    }
    return this.getParent(id);
  },

  async updateParent() {
    return unsupported("Editing parents isn't available on the school's server yet.");
  },

  async setParentStatus() {
    return unsupported("Activating or deactivating parents isn't available on the school's server yet.");
  },

  async listEmployees(kind: EmployeeKind, query: EmployeeQuery = {}) {
    teachersOnly(kind);
    const rows = (await all("teachers", "Unable to load teachers."))
      .map(employeeRow)
      .filter((row) => statusMatches(row.status, query.status))
      .filter((row) => matches(query.q, row.name, row.email, row.mobile))
      .sort((a, b) => a.name.localeCompare(b.name));
    return slice(rows, query.page, query.pageSize);
  },

  async listDepartments() {
    return [];
  },

  async getEmployee(kind, id) {
    teachersOnly(kind);
    const row = (await all("teachers", "Unable to load this teacher.")).find((item) => num(item.id) === id);
    if (!row) throw new AcademicApiError(404, "Teacher not found");
    return employeeDetail(row);
  },

  async createEmployee(kind, input) {
    teachersOnly(kind);
    const saved = await send<Raw>(
      "POST",
      "/teachers",
      { first_name: input.first_name, last_name: input.last_name, email: input.email, mobile: input.mobile, qualification: input.qualification ?? null },
      "Unable to add the teacher.",
    );
    return employeeDetail({ ...saved, qualification: input.qualification });
  },

  async updateEmployee() {
    return unsupported("Editing teachers isn't available on the school's server yet.");
  },

  async setEmployeeStatus() {
    return unsupported("Activating or deactivating teachers isn't available on the school's server yet.");
  },

  async uploadPhoto() {
    return unsupported(NO_FILES);
  },
  async uploadDocument() {
    return unsupported(NO_FILES);
  },
  async deleteDocument() {
    return unsupported(NO_FILES);
  },
};
