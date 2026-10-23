/**
 * Live people client for the backend's School Admin routes:
 *   /school-admin/academics/students   list (page, q), create, PATCH (incl. status)
 *   /school-admin/academics/parents    list (page, q), create
 *   /school-admin/teachers, /school-admin/staff
 *       list (page, q, status, department, employment_status), create, GET/PATCH /{id},
 *       PATCH /{id}/status, photo and documents (/{id}/photo, /{id}/documents[/{doc}[/download]])
 * The server derives the school from the Bearer session, so no request sends a school_id.
 *
 * The student and parent routes have no detail, filter or sort parameters, so this client reads
 * the full list (at most 1,000 rows) and filters, sorts and finds records here. Session, class
 * and section names come from the academics routes. Anything the routes can't store throws a
 * clear error; the pages hide those controls (peopleSupport in lib/people/index.ts).
 */
import { api, apiBlobUrl } from "@/lib/api";
import { AcademicApiError, errorFromResponse } from "@/lib/academics/errors";
import type {
  ChildLink,
  Employee,
  EmployeeInput,
  EmployeeKind,
  EmployeeQuery,
  EmployeeRow,
  FileOwner,
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
  StoredFile,
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

// ---------- teachers and staff ----------

const EMPLOYEE_ROUTE: Record<EmployeeKind, string> = { teachers: "/school-admin/teachers", staff: "/school-admin/staff" };
const CODE_PREFIX: Record<EmployeeKind, string> = { teachers: "TCH", staff: "STF" };
const EMPLOYEE_NOUN: Record<EmployeeKind, string> = { teachers: "teacher", staff: "staff member" };

/** Calls a route outside /school-admin/academics, e.g. /school-admin/teachers. */
async function requestAt<T>(path: string, init: RequestInit, fallback: string): Promise<T> {
  let result;
  try {
    result = await api<T>(path, init);
  } catch {
    throw errorFromResponse(0, null, fallback);
  }
  if (!result.ok) throw errorFromResponse(result.status, result.data, fallback);
  return result.data;
}

async function allAt(path: string, params: Record<string, string>, fallback: string): Promise<Raw[]> {
  const rows: Raw[] = [];
  for (let page = 1; page <= MAX_PAGES; page += 1) {
    const search = new URLSearchParams({ ...params, page: String(page), page_size: String(PAGE_SIZE) });
    const data = await requestAt<Raw>(`${path}?${search}`, { method: "GET" }, fallback);
    const items = Array.isArray(data.items) ? (data.items as Raw[]) : [];
    rows.push(...items);
    if (items.length === 0 || rows.length >= Number(data.total ?? rows.length)) break;
  }
  return rows;
}

// Photos need the sign-in token, so they're fetched once and shown from blob: URLs.
const photoCache = new Map<string, Promise<string | null>>();

function photoFor(kind: EmployeeKind, row: Raw): Promise<string | null> {
  if (!row.image) return Promise.resolve(null);
  const key = `${kind}:${num(row.id)}:${str(row.image)}`;
  if (!photoCache.has(key)) {
    photoCache.set(key, apiBlobUrl(`${EMPLOYEE_ROUTE[kind]}/${num(row.id)}/photo`).catch(() => null));
  }
  return photoCache.get(key) as Promise<string | null>;
}

function forgetPhoto(kind: EmployeeKind, id: number) {
  for (const key of photoCache.keys()) if (key.startsWith(`${kind}:${id}:`)) photoCache.delete(key);
}

function employeeRow(row: Raw, photoUrl: string | null): EmployeeRow {
  return {
    id: num(row.id),
    employee_code: str(row.employee_id),
    first_name: str(row.first_name),
    last_name: str(row.last_name),
    name: fullName(row),
    email: str(row.email),
    mobile: str(row.mobile),
    department: str(row.department),
    designation: str(row.designation),
    joining_date: str(row.joining_date),
    employment_type: str(row.employment_status),
    photo_url: photoUrl,
    status: status(row.status),
  };
}

const CATEGORY_LABEL: Record<string, string> = { resume: "Resume", id_proof: "ID proof", certificate: "Certificate", other: "Other" };

/** The backend files documents by category; the title the admin typed picks the closest one. */
function categoryFor(title: string): string {
  const text = title.toLowerCase();
  if (/resume|\bcv\b|curriculum/.test(text)) return "resume";
  if (/\bid\b|id proof|aadhaar|aadhar|\bpan\b|passport|identity|licen[cs]e|voter/.test(text)) return "id_proof";
  if (/certificate|degree|diploma|mark ?sheet|qualification|b\.?ed|experience/.test(text)) return "certificate";
  return "other";
}

function storedFile(kind: EmployeeKind, ownerId: number, row: Raw): StoredFile {
  const category = str(row.category);
  return {
    id: num(row.id),
    title: CATEGORY_LABEL[category] ?? category,
    file_name: str(row.original_filename) || `${category}-${num(row.id)}`,
    content_type: str(row.content_type),
    size: num(row.size_bytes),
    // Downloads need the sign-in token; StoredDocuments fetches auth: links before opening them.
    url: `auth:${EMPLOYEE_ROUTE[kind]}/${ownerId}/documents/${num(row.id)}/download`,
    uploaded_at: str(row.created_at),
  };
}

async function employeeDetail(kind: EmployeeKind, row: Raw): Promise<Employee> {
  const id = num(row.id);
  const [photo, documents] = await Promise.all([
    photoFor(kind, row),
    allAt(`${EMPLOYEE_ROUTE[kind]}/${id}/documents`, {}, "Unable to load documents."),
  ]);
  return {
    ...employeeRow(row, photo),
    gender: (str(row.gender) || null) as Gender | null,
    dob: str(row.dob) || null,
    qualification: str(row.qualification) || null,
    current_address: str(row.current_address) || null,
    documents: documents.filter((doc) => str(doc.category) !== "profile_photo").map((doc) => storedFile(kind, id, doc)),
  };
}

async function nextEmployeeCode(kind: EmployeeKind): Promise<string> {
  const prefix = CODE_PREFIX[kind];
  const used = (await allAt(EMPLOYEE_ROUTE[kind], {}, "Unable to load employee IDs."))
    .map((row) => str(row.employee_id).toUpperCase())
    .filter((code) => code.startsWith(prefix))
    .map((code) => Number(code.slice(prefix.length)) || 0);
  return `${prefix}${String(Math.max(0, ...used) + 1).padStart(4, "0")}`;
}

function employeeBody(input: EmployeeInput, code: string) {
  return {
    first_name: input.first_name,
    last_name: input.last_name,
    email: input.email,
    mobile: input.mobile || null,
    gender: input.gender || null,
    dob: input.dob || null,
    current_address: input.current_address || null,
    qualification: input.qualification || null,
    employee_id: code || null,
    joining_date: input.joining_date || null,
    employment_status: input.employment_type || null,
    department: input.department || null,
    designation: input.designation || null,
  };
}

function employeeOwner(owner: FileOwner): EmployeeKind {
  if (owner === "students") unsupported(NO_STUDENT_FILES);
  return owner;
}

const NO_STUDENT_FILES = "Student photos and documents can't be uploaded to the school's server yet.";

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
    const params = new URLSearchParams({
      page: String(query.page ?? 1),
      page_size: String(Math.min(query.pageSize ?? 20, PAGE_SIZE)),
    });
    if (query.q?.trim()) params.set("q", query.q.trim());
    if (query.status === "0" || query.status === "1") params.set("status", query.status);
    if (query.department?.trim()) params.set("department", query.department.trim());
    if (query.employmentType) params.set("employment_status", query.employmentType);
    const data = await requestAt<Raw>(`${EMPLOYEE_ROUTE[kind]}?${params}`, { method: "GET" }, `Unable to load ${kind}.`);
    const rows = Array.isArray(data.items) ? (data.items as Raw[]) : [];
    const items = await Promise.all(rows.map(async (row) => employeeRow(row, await photoFor(kind, row))));
    return { items, total: num(data.total ?? items.length), page: num(data.page ?? 1), page_size: num(data.page_size ?? items.length) };
  },

  async listDepartments(kind) {
    // There's no department list route, so the names come from the employees themselves.
    const rows = await allAt(EMPLOYEE_ROUTE[kind], {}, "Unable to load departments.");
    return [...new Set(rows.map((row) => str(row.department).trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b));
  },

  async getEmployee(kind, id) {
    const row = await requestAt<Raw>(`${EMPLOYEE_ROUTE[kind]}/${id}`, { method: "GET" }, `Unable to load this ${EMPLOYEE_NOUN[kind]}.`);
    return employeeDetail(kind, row);
  },

  async createEmployee(kind, input) {
    if (!input.password || input.password.length < 8) {
      throw new AcademicApiError(422, "Check the highlighted fields.", { password: "Enter a password of at least 8 characters." });
    }
    const code = input.employee_code?.trim() || (await nextEmployeeCode(kind));
    const created = await requestAt<Raw>(
      EMPLOYEE_ROUTE[kind],
      { method: "POST", body: JSON.stringify({ ...employeeBody(input, code), password: input.password }) },
      `Unable to add the ${EMPLOYEE_NOUN[kind]}.`,
    );
    // New accounts start active on the server.
    const saved =
      input.status === 0
        ? await requestAt<Raw>(`${EMPLOYEE_ROUTE[kind]}/${num(created.id)}/status`, { method: "PATCH", body: JSON.stringify({ status: 0 }) }, "Unable to save the status.")
        : created;
    return employeeDetail(kind, saved);
  },

  async updateEmployee(kind, id, input) {
    const route = `${EMPLOYEE_ROUTE[kind]}/${id}`;
    let saved = await requestAt<Raw>(route, { method: "PATCH", body: JSON.stringify(employeeBody(input, input.employee_code?.trim() ?? "")) }, `Unable to save the ${EMPLOYEE_NOUN[kind]}.`);
    // Account status has its own route.
    if (status(saved.status) !== input.status) {
      saved = await requestAt<Raw>(`${route}/status`, { method: "PATCH", body: JSON.stringify({ status: input.status }) }, "Unable to save the status.");
    }
    return employeeDetail(kind, saved);
  },

  async setEmployeeStatus(kind, id, value) {
    const saved = await requestAt<Raw>(`${EMPLOYEE_ROUTE[kind]}/${id}/status`, { method: "PATCH", body: JSON.stringify({ status: value }) }, "Unable to change the status.");
    return employeeDetail(kind, saved);
  },

  async uploadPhoto(owner, id, file) {
    const kind = employeeOwner(owner);
    const form = new FormData();
    form.set("file", file);
    await requestAt<Raw>(`${EMPLOYEE_ROUTE[kind]}/${id}/photo`, { method: "POST", body: form }, "Unable to upload the photo.");
    forgetPhoto(kind, id);
    return { photo_url: await apiBlobUrl(`${EMPLOYEE_ROUTE[kind]}/${id}/photo`).catch(() => null) };
  },

  async uploadDocument(owner, id, file, title) {
    const kind = employeeOwner(owner);
    const form = new FormData();
    form.set("file", file);
    form.set("category", categoryFor(title));
    const row = await requestAt<Raw>(`${EMPLOYEE_ROUTE[kind]}/${id}/documents`, { method: "POST", body: form }, `Unable to upload ${file.name}.`);
    return storedFile(kind, id, row);
  },

  async deleteDocument(owner, id, documentId) {
    const kind = employeeOwner(owner);
    await requestAt<Raw>(`${EMPLOYEE_ROUTE[kind]}/${id}/documents/${documentId}`, { method: "DELETE" }, "Unable to remove the document.");
  },
};
