/**
 * Live people client for the backend's School Admin routes:
 *   /school-admin/students   list (q, status, session, class, section, parent, sort), create,
 *       GET/PATCH /{id}, PATCH /{id}/status, guardians (POST /{id}/guardians, DELETE
 *       /{id}/guardians/{parent}), photo and documents (/{id}/photo, /{id}/documents[/{doc}[/download]])
 *   /school-admin/parents    list (q, status, email, mobile), create (with linked students),
 *       GET/PATCH /{id}, PATCH /{id}/status
 *   /school-admin/teachers, /school-admin/staff
 *       list (page, q, status, department, employment_status), create, GET/PATCH /{id},
 *       PATCH /{id}/status, /departments, photo and documents
 * The server derives the school from the Bearer session, so no request sends a school_id.
 * New parents get a server-generated password and set their own through a reset link.
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
  Parent,
  ParentCreateInput,
  ParentInput,
  ParentQuery,
  PeopleService,
  RecordStatus,
  Relationship,
  Student,
  StudentCreateInput,
  StudentInput,
  StudentQuery,
  StoredFile,
  StudentRow,
} from "@/lib/people/types";

/** The backend caps page_size at 50. */
const PAGE_SIZE = 50;
const MAX_PAGES = 20;

type Raw = Record<string, unknown>;

function str(value: unknown): string {
  return typeof value === "string" ? value : value === null || value === undefined ? "" : String(value);
}

function num(value: unknown): number {
  return typeof value === "number" ? value : Number(value ?? 0);
}

function optStr(value: unknown): string | null {
  const text = str(value).trim();
  return text ? text : null;
}

function status(value: unknown): RecordStatus {
  return value === 0 || value === "0" ? 0 : 1;
}

function fullName(row: Raw): string {
  return str(row.name) || `${str(row.first_name)} ${str(row.last_name)}`.trim();
}

/** Calls a /api/v1 route, e.g. /school-admin/students. */
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

function json(method: "POST" | "PATCH" | "DELETE", body?: unknown): RequestInit {
  return body === undefined ? { method } : { method, body: JSON.stringify(body) };
}

// ---------- field errors ----------

/**
 * The server answers most rule breaks with one sentence ("dob cannot be in the future",
 * "Roll number is already used in this class section and session"). This puts the sentence
 * under the field it's about, so the form highlights it as well as showing it at the top.
 */
function onField(error: unknown, form: "student" | "parent"): unknown {
  if (!(error instanceof AcademicApiError) || Object.keys(error.fieldErrors).length) return error;
  const message = error.message;
  const guardian = form === "student" ? "guardian." : "";
  const rules: [RegExp, string][] = [
    [/^Roll number|^roll_number/i, "roll_number"],
    [/^Admission number|^admission_no/i, "admission_no"],
    [/^A student email/i, "email"],
    // The server doesn't say which of the two clashed, so both fields show it.
    [/already registered with this email or phone/i, `${guardian}email,${guardian}mobile`],
    [/^Email is already used/i, `${guardian}email`],
    [/^Mobile is already used/i, `${guardian}mobile`],
    [/^student must be between|^dob /i, "dob"],
    [/^admission_date /i, "admission_date"],
    [/^relationship must/i, form === "student" ? "guardian.relationship" : "students"],
    [/^guardian\.parent_id/i, "guardian.parent_id"],
    [/^guardian\.(\w+)/i, ""],
    [/^(gender|current_address|permanent_address|session_year_id|class_section_id|first_name|last_name|mobile|email|occupation) /i, ""],
  ];
  for (const [pattern, field] of rules) {
    const match = message.match(pattern);
    if (!match) continue;
    // An empty field means "the field the sentence starts with" (guardian.* keeps its prefix).
    const key = field || (match[0].toLowerCase().startsWith("guardian.") ? `guardian.${match[1]}` : match[1].toLowerCase());
    const text = message.charAt(0).toUpperCase() + message.slice(1).replace(/_/g, " ");
    return new AcademicApiError(error.status, text, Object.fromEntries(key.split(",").map((name) => [name, text])));
  }
  return error;
}

async function withFields<T>(work: Promise<T>, form: "student" | "parent"): Promise<T> {
  try {
    return await work;
  } catch (caught) {
    throw onField(caught, form);
  }
}

// ---------- photos ----------

// Photos need the sign-in token, so they're fetched once and shown from blob: URLs.
const photoCache = new Map<string, Promise<string | null>>();

/** photo_url from the server is an /api/v1 path (or empty when there's no photo). */
function photoFrom(key: string, path: string | null): Promise<string | null> {
  if (!path) return Promise.resolve(null);
  const route = path.replace(/^\/api\/v1/, "");
  const cacheKey = `${key}:${route}`;
  if (!photoCache.has(cacheKey)) photoCache.set(cacheKey, apiBlobUrl(route).catch(() => null));
  return photoCache.get(cacheKey) as Promise<string | null>;
}

function forgetPhotos(prefix: string) {
  for (const key of photoCache.keys()) if (key.startsWith(prefix)) photoCache.delete(key);
}

// ---------- students ----------

const STUDENTS = "/school-admin/students";

async function studentRow(row: Raw): Promise<StudentRow> {
  const id = num(row.id);
  return {
    id,
    admission_no: str(row.admission_no),
    first_name: str(row.first_name),
    last_name: str(row.last_name),
    name: fullName(row),
    session_year_id: num(row.session_year_id),
    session_name: str(row.session_name),
    class_id: num(row.class_id),
    class_name: str(row.class_name),
    class_section_id: num(row.class_section_id),
    section_name: str(row.section_name),
    roll_number: row.roll_number === null || row.roll_number === undefined ? null : num(row.roll_number),
    guardian_name: optStr(row.guardian_name),
    guardian_mobile: optStr(row.guardian_mobile),
    admission_date: str(row.admission_date),
    photo_url: await photoFrom(`students:${id}`, optStr(row.photo_url)),
    status: status(row.status),
  };
}

function storedDocument(row: Raw, fallbackUrl: string): StoredFile {
  const path = str(row.url).replace(/^\/api\/v1/, "") || fallbackUrl;
  return {
    id: num(row.id),
    title: str(row.title) || str(row.original_filename) || "Document",
    file_name: str(row.file_name) || str(row.original_filename) || `document-${num(row.id)}`,
    content_type: str(row.content_type),
    size: num(row.size ?? row.size_bytes),
    // Downloads need the sign-in token; StoredDocuments fetches auth: links before opening them.
    url: `auth:${path}`,
    uploaded_at: str(row.uploaded_at) || str(row.created_at),
  };
}

async function studentDetail(row: Raw): Promise<Student> {
  const base = await studentRow(row);
  const guardians: GuardianLink[] = (Array.isArray(row.guardians) ? (row.guardians as Raw[]) : []).map((item) => ({
    parent_id: num(item.parent_id),
    name: str(item.name),
    email: optStr(item.email),
    mobile: optStr(item.mobile),
    relationship: (str(item.relationship) || "Guardian") as Relationship,
    is_primary: Boolean(item.is_primary),
  }));
  const documents = (Array.isArray(row.documents) ? (row.documents as Raw[]) : []).map((doc) =>
    storedDocument(doc, `${STUDENTS}/${base.id}/documents/${num(doc.id)}/download`),
  );
  return {
    ...base,
    dob: str(row.dob),
    gender: (str(row.gender) || "") as Gender,
    email: optStr(row.email),
    mobile: optStr(row.mobile),
    current_address: str(row.current_address),
    permanent_address: optStr(row.permanent_address),
    guardians,
    documents,
  };
}

function studentBody(input: StudentInput) {
  return {
    first_name: input.first_name.trim(),
    last_name: input.last_name.trim(),
    dob: input.dob,
    gender: input.gender,
    admission_date: input.admission_date,
    session_year_id: input.session_year_id,
    class_section_id: input.class_section_id,
    roll_number: input.roll_number ?? null,
    email: input.email?.trim() || null,
    mobile: input.mobile?.trim() || null,
    current_address: input.current_address.trim(),
    permanent_address: input.permanent_address?.trim() || null,
    status: input.status,
  };
}

// ---------- parents ----------

const PARENTS = "/school-admin/parents";

function parentOut(row: Raw): Parent {
  const children: ChildLink[] = (Array.isArray(row.children) ? (row.children as Raw[]) : []).map((item) => ({
    student_id: num(item.student_id),
    name: str(item.name),
    admission_no: str(item.admission_no),
    class_name: str(item.class_name),
    section_name: str(item.section_name),
    relationship: (str(item.relationship) || "Guardian") as Relationship,
    is_primary: Boolean(item.is_primary),
    status: status(item.status),
  }));
  return {
    id: num(row.id),
    first_name: str(row.first_name),
    last_name: str(row.last_name),
    name: fullName(row),
    email: str(row.email),
    mobile: str(row.mobile),
    current_address: optStr(row.current_address),
    occupation: optStr(row.occupation),
    status: status(row.status),
    children: children.sort((a, b) => a.name.localeCompare(b.name)),
  };
}

function parentBody(input: ParentInput) {
  return {
    first_name: input.first_name.trim(),
    last_name: input.last_name.trim(),
    email: input.email.trim(),
    mobile: input.mobile.trim(),
    current_address: input.current_address?.trim() || null,
    occupation: input.occupation?.trim() || null,
    status: input.status,
  };
}

// ---------- teachers and staff ----------

const EMPLOYEE_ROUTE: Record<EmployeeKind, string> = { teachers: "/school-admin/teachers", staff: "/school-admin/staff" };
const CODE_PREFIX: Record<EmployeeKind, string> = { teachers: "TCH", staff: "STF" };
const EMPLOYEE_NOUN: Record<EmployeeKind, string> = { teachers: "teacher", staff: "staff member" };

function photoFor(kind: EmployeeKind, row: Raw): Promise<string | null> {
  if (!row.image) return Promise.resolve(null);
  return photoFrom(`${kind}:${num(row.id)}:${str(row.image)}`, `${EMPLOYEE_ROUTE[kind]}/${num(row.id)}/photo`);
}

function forgetPhoto(kind: EmployeeKind, id: number) {
  forgetPhotos(`${kind}:${id}:`);
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

/** The backend also files documents by category; the title the admin typed picks the closest one. */
function categoryFor(title: string): string {
  const text = title.toLowerCase();
  if (/resume|\bcv\b|curriculum/.test(text)) return "resume";
  if (/\bid\b|id proof|aadhaar|aadhar|\bpan\b|passport|identity|licen[cs]e|voter/.test(text)) return "id_proof";
  if (/certificate|degree|diploma|mark ?sheet|qualification|b\.?ed|experience/.test(text)) return "certificate";
  return "other";
}

function storedFile(kind: EmployeeKind, ownerId: number, row: Raw): StoredFile {
  const file = storedDocument(row, `${EMPLOYEE_ROUTE[kind]}/${ownerId}/documents/${num(row.id)}/download`);
  // Older rows have no title; show their category instead.
  const category = str(row.category);
  return str(row.title) ? file : { ...file, title: CATEGORY_LABEL[category] ?? (category || file.title) };
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

/** Where an owner's photo and documents live. */
function fileRoute(owner: FileOwner): string {
  return owner === "students" ? STUDENTS : EMPLOYEE_ROUTE[owner];
}

export const httpPeopleService: PeopleService = {
  async listStudents(query: StudentQuery = {}) {
    const params = new URLSearchParams({ page: String(query.page ?? 1), page_size: String(Math.min(query.pageSize ?? 20, PAGE_SIZE)) });
    if (query.q?.trim()) params.set("q", query.q.trim());
    if (query.status === "0" || query.status === "1") params.set("status", query.status);
    if (query.sessionYearId) params.set("session_year_id", String(query.sessionYearId));
    if (query.classId) params.set("class_id", String(query.classId));
    if (query.classSectionId) params.set("class_section_id", String(query.classSectionId));
    if (query.parentId) params.set("parent_id", String(query.parentId));
    if (query.sort) params.set("sort", query.sort);
    if (query.order) params.set("order", query.order);
    const data = await requestAt<Raw>(`${STUDENTS}?${params}`, { method: "GET" }, "Unable to load students.");
    const rows = Array.isArray(data.items) ? (data.items as Raw[]) : [];
    const items = await Promise.all(rows.map(studentRow));
    return { items, total: num(data.total ?? items.length), page: num(data.page ?? 1), page_size: num(data.page_size ?? items.length) };
  },

  async getStudent(id) {
    return studentDetail(await requestAt<Raw>(`${STUDENTS}/${id}`, { method: "GET" }, "Unable to load this student."));
  },

  async createStudent(input: StudentCreateInput) {
    const guardian =
      "parent_id" in input.guardian
        ? { parent_id: Number(input.guardian.parent_id), relationship: input.guardian.relationship }
        : {
            relationship: input.guardian.relationship,
            first_name: input.guardian.first_name.trim(),
            last_name: input.guardian.last_name.trim(),
            email: input.guardian.email.trim(),
            mobile: input.guardian.mobile.trim(),
          };
    const body = { ...studentBody(input), admission_no: input.admission_no?.trim() || null, guardian };
    const saved = await withFields(requestAt<Raw>(STUDENTS, json("POST", body), "Unable to admit the student."), "student");
    return studentDetail(saved);
  },

  async updateStudent(id, input: StudentInput) {
    const body = { ...studentBody(input), admission_no: (input.admission_no ?? "").trim() };
    return studentDetail(await withFields(requestAt<Raw>(`${STUDENTS}/${id}`, json("PATCH", body), "Unable to save the student."), "student"));
  },

  async setStudentStatus(id, value: RecordStatus) {
    return studentDetail(await requestAt<Raw>(`${STUDENTS}/${id}/status`, json("PATCH", { status: value }), "Unable to change the student's status."));
  },

  async linkGuardian(studentId, link) {
    const body = { parent_id: link.parent_id, relationship: link.relationship, is_primary: link.is_primary ?? null };
    return studentDetail(await requestAt<Raw>(`${STUDENTS}/${studentId}/guardians`, json("POST", body), "Unable to link the guardian."));
  },

  async unlinkGuardian(studentId, parentId) {
    return studentDetail(await requestAt<Raw>(`${STUDENTS}/${studentId}/guardians/${parentId}`, json("DELETE"), "Unable to remove the guardian."));
  },

  async listParents(query: ParentQuery = {}) {
    const params = new URLSearchParams({ page: String(query.page ?? 1), page_size: String(Math.min(query.pageSize ?? 20, PAGE_SIZE)) });
    if (query.q?.trim()) params.set("q", query.q.trim());
    if (query.status === "0" || query.status === "1") params.set("status", query.status);
    if (query.email?.trim()) params.set("email", query.email.trim());
    if (query.mobile?.trim()) params.set("mobile", query.mobile.trim());
    const data = await requestAt<Raw>(`${PARENTS}?${params}`, { method: "GET" }, "Unable to load parents.");
    const items = (Array.isArray(data.items) ? (data.items as Raw[]) : []).map(parentOut);
    return { items, total: num(data.total ?? items.length), page: num(data.page ?? 1), page_size: num(data.page_size ?? items.length) };
  },

  async getParent(id) {
    return parentOut(await requestAt<Raw>(`${PARENTS}/${id}`, { method: "GET" }, "Unable to load this parent."));
  },

  async createParent(input: ParentCreateInput) {
    const body = { ...parentBody(input), students: (input.students ?? []).map((link) => ({ student_id: link.student_id, relationship: link.relationship })) };
    return parentOut(await withFields(requestAt<Raw>(PARENTS, json("POST", body), "Unable to add the parent."), "parent"));
  },

  async updateParent(id, input: ParentInput) {
    return parentOut(await withFields(requestAt<Raw>(`${PARENTS}/${id}`, json("PATCH", parentBody(input)), "Unable to save the parent."), "parent"));
  },

  async setParentStatus(id, value: RecordStatus) {
    return parentOut(await requestAt<Raw>(`${PARENTS}/${id}/status`, json("PATCH", { status: value }), "Unable to change the parent's status."));
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
    const data = await requestAt<Raw>(`${EMPLOYEE_ROUTE[kind]}/departments`, { method: "GET" }, "Unable to load departments.");
    return (Array.isArray(data.items) ? (data.items as unknown[]) : []).map(str).filter(Boolean);
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
    const route = `${fileRoute(owner)}/${id}/photo`;
    const form = new FormData();
    form.set("file", file);
    await requestAt<Raw>(route, { method: "POST", body: form }, "Unable to upload the photo.");
    forgetPhotos(`${owner}:${id}:`);
    return { photo_url: await apiBlobUrl(route).catch(() => null) };
  },

  async uploadDocument(owner, id, file, title) {
    const form = new FormData();
    form.set("file", file);
    form.set("title", title.trim());
    form.set("category", owner === "students" ? "other" : categoryFor(title));
    const row = await requestAt<Raw>(`${fileRoute(owner)}/${id}/documents`, { method: "POST", body: form }, `Unable to upload ${file.name}.`);
    return owner === "students" ? storedDocument(row, `${STUDENTS}/${id}/documents/${num(row.id)}/download`) : storedFile(owner, id, row);
  },

  async deleteDocument(owner, id, documentId) {
    await requestAt<Raw>(`${fileRoute(owner)}/${id}/documents/${documentId}`, { method: "DELETE" }, "Unable to remove the document.");
  },
};
