/**
 * Live people client for the FastAPI routes under `/api/v1/school-admin`.
 * The server derives the school from the Bearer session, so no request sends a school_id.
 * See backend/docs/PEOPLE_API_CONTRACT.md for the shapes this client expects.
 */
import { api } from "@/lib/api";
import { errorFromResponse } from "@/lib/academics/errors";
import type {
  Employee,
  EmployeeInput,
  EmployeeKind,
  EmployeeQuery,
  EmployeeRow,
  FileOwner,
  Page,
  Parent,
  ParentCreateInput,
  ParentInput,
  ParentQuery,
  PeopleService,
  RecordStatus,
  StoredFile,
  Student,
  StudentCreateInput,
  StudentInput,
  StudentQuery,
  StudentRow,
} from "@/lib/people/types";

const BASE = "/school-admin";
/** The backend caps page_size at 50. */
const MAX_PAGE_SIZE = 50;

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

function send<T>(method: "POST" | "PATCH" | "DELETE", path: string, body: unknown, fallback: string) {
  return request<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) }, fallback);
}

function upload<T>(path: string, form: FormData, fallback: string) {
  return request<T>(path, { method: "POST", body: form }, fallback);
}

function paging(query: { page?: number; pageSize?: number; q?: string; status?: string }) {
  return {
    page: query.page ?? 1,
    page_size: Math.min(query.pageSize ?? 20, MAX_PAGE_SIZE),
    q: query.q?.trim(),
    status: query.status,
  };
}

// The pages read these arrays and names directly, so fill them in if a response leaves them out.
function named<T extends { first_name?: string; last_name?: string; name?: string }>(row: T): T & { name: string } {
  return { ...row, name: row.name || `${row.first_name ?? ""} ${row.last_name ?? ""}`.trim() };
}

function toStudent(row: Student): Student {
  return named({ ...row, guardians: row.guardians ?? [], documents: row.documents ?? [] });
}

function toParent(row: Parent): Parent {
  return named({ ...row, children: row.children ?? [] });
}

function toEmployee(row: Employee): Employee {
  return named({ ...row, documents: row.documents ?? [] });
}

function mapPage<T>(data: Page<T>, map: (row: T) => T): Page<T> {
  const items = Array.isArray(data.items) ? data.items.map(map) : [];
  return { items, total: data.total ?? items.length, page: data.page ?? 1, page_size: data.page_size ?? items.length };
}

export const httpPeopleService: PeopleService = {
  async listStudents(query: StudentQuery = {}) {
    const data = await get<Page<StudentRow>>(
      "/students",
      {
        ...paging(query),
        session_year_id: query.sessionYearId,
        class_id: query.classId,
        class_section_id: query.classSectionId,
        parent_id: query.parentId,
        sort: query.sort,
        order: query.order,
      },
      "Unable to load students.",
    );
    return mapPage(data, named);
  },
  async getStudent(id) {
    return toStudent(await get<Student>(`/students/${id}`, {}, "Unable to load this student."));
  },
  async createStudent(input: StudentCreateInput) {
    return toStudent(await send<Student>("POST", "/students", input, "Unable to admit the student."));
  },
  async updateStudent(id, input: StudentInput) {
    return toStudent(await send<Student>("PATCH", `/students/${id}`, input, "Unable to save the student."));
  },
  async setStudentStatus(id, status: RecordStatus) {
    return toStudent(await send<Student>("PATCH", `/students/${id}/status`, { status }, "Unable to change the student's status."));
  },
  async linkGuardian(studentId, link) {
    return toStudent(await send<Student>("POST", `/students/${studentId}/guardians`, link, "Unable to link the guardian."));
  },
  async unlinkGuardian(studentId, parentId) {
    return toStudent(await send<Student>("DELETE", `/students/${studentId}/guardians/${parentId}`, undefined, "Unable to remove the guardian."));
  },

  async listParents(query: ParentQuery = {}) {
    const data = await get<Page<Parent>>("/parents", { ...paging(query), email: query.email?.trim(), mobile: query.mobile?.trim() }, "Unable to load parents.");
    return mapPage(data, toParent);
  },
  async getParent(id) {
    return toParent(await get<Parent>(`/parents/${id}`, {}, "Unable to load this parent."));
  },
  async createParent(input: ParentCreateInput) {
    return toParent(await send<Parent>("POST", "/parents", input, "Unable to add the parent."));
  },
  async updateParent(id, input: ParentInput) {
    return toParent(await send<Parent>("PATCH", `/parents/${id}`, input, "Unable to save the parent."));
  },
  async setParentStatus(id, status) {
    return toParent(await send<Parent>("PATCH", `/parents/${id}/status`, { status }, "Unable to change the parent's status."));
  },

  async listEmployees(kind: EmployeeKind, query: EmployeeQuery = {}) {
    const data = await get<Page<EmployeeRow>>(
      `/${kind}`,
      { ...paging(query), department: query.department, employment_type: query.employmentType },
      `Unable to load ${kind}.`,
    );
    return mapPage(data, named);
  },
  async listDepartments(kind) {
    const data = await get<{ items?: string[] }>(`/${kind}/departments`, {}, "Unable to load departments.");
    return data.items ?? [];
  },
  async getEmployee(kind, id) {
    return toEmployee(await get<Employee>(`/${kind}/${id}`, {}, "Unable to load this record."));
  },
  async createEmployee(kind, input: EmployeeInput) {
    return toEmployee(await send<Employee>("POST", `/${kind}`, input, "Unable to save the record."));
  },
  async updateEmployee(kind, id, input: EmployeeInput) {
    return toEmployee(await send<Employee>("PATCH", `/${kind}/${id}`, input, "Unable to save the record."));
  },
  async setEmployeeStatus(kind, id, status) {
    return toEmployee(await send<Employee>("PATCH", `/${kind}/${id}/status`, { status }, "Unable to change the status."));
  },

  uploadPhoto(owner: FileOwner, id, file) {
    const form = new FormData();
    form.set("file", file);
    return upload<{ photo_url: string | null }>(`/${owner}/${id}/photo`, form, "Unable to upload the photo.");
  },
  uploadDocument(owner, id, file, title) {
    const form = new FormData();
    form.set("file", file);
    form.set("title", title);
    return upload<StoredFile>(`/${owner}/${id}/documents`, form, `Unable to upload ${file.name}.`);
  },
  async deleteDocument(owner, id, documentId) {
    await send<unknown>("DELETE", `/${owner}/${id}/documents/${documentId}`, undefined, "Unable to remove the document.");
  },
};
