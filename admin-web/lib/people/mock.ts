/**
 * Mock people client. It follows the same contract and validation rules as the live API
 * (backend/docs/PEOPLE_API_CONTRACT.md) so pages behave the same before and after the switch.
 * Data starts from mock-data.json and is kept in this browser's localStorage.
 *
 * Records from another school are in the seed on purpose: they never appear in a list, and
 * opening one by id returns 404, the same as the live API.
 */
import seed from "@/lib/people/mock-data.json";
import { AcademicApiError } from "@/lib/academics/errors";
import { mockAcademicSnapshot } from "@/lib/academics/mock";
import {
  DOCUMENTS_PER_RECORD,
  documentProblem,
  fileType,
  photoProblem,
} from "@/lib/people/files";
import type {
  ChildLink,
  Employee,
  EmployeeInput,
  EmployeeKind,
  EmployeeQuery,
  EmployeeRow,
  EmploymentType,
  FileOwner,
  Gender,
  GuardianChoice,
  GuardianLink,
  Page,
  Parent,
  ParentCreateInput,
  ParentInput,
  ParentQuery,
  PeopleService,
  RecordStatus,
  Relationship,
  StoredFile,
  Student,
  StudentCreateInput,
  StudentInput,
  StudentQuery,
  StudentRow,
} from "@/lib/people/types";
import { EMPLOYMENT_TYPES, GENDERS, RELATIONSHIPS } from "@/lib/people/types";

type StudentRecord = {
  id: number;
  school_id: number;
  admission_no: string;
  first_name: string;
  last_name: string;
  dob: string;
  gender: string;
  email: string | null;
  mobile: string | null;
  current_address: string;
  permanent_address: string | null;
  session_year_id: number;
  class_section_id: number;
  roll_number: number | null;
  admission_date: string;
  status: number;
  photo_url: string | null;
  documents: StoredFile[];
};

type ParentRecord = {
  id: number;
  school_id: number;
  first_name: string;
  last_name: string;
  email: string;
  mobile: string;
  current_address: string | null;
  occupation: string | null;
  status: number;
};

type LinkRecord = { student_id: number; parent_id: number; relationship: string; is_primary: boolean };

type EmployeeRecord = {
  id: number;
  school_id: number;
  kind: string;
  employee_code: string;
  first_name: string;
  last_name: string;
  email: string;
  mobile: string;
  gender: string | null;
  dob: string | null;
  qualification: string | null;
  department: string;
  designation: string;
  joining_date: string;
  employment_type: string;
  current_address: string | null;
  status: number;
  photo_url: string | null;
  documents: StoredFile[];
};

type Db = {
  school_id: number;
  students: StudentRecord[];
  parents: ParentRecord[];
  guardian_links: LinkRecord[];
  employees: EmployeeRecord[];
  next_file_id: number;
};

const STORAGE_KEY = "people-mock-db-v1";
const LATENCY_MS = 0;
/** Files bigger than this stay in memory only, so a few uploads can't fill localStorage. */
const PERSIST_FILE_BYTES = 400 * 1024;

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
    // Storage can be full or unavailable (private mode). The in-memory copy still works for this tab.
  }
}

/** Clears local changes and restores mock-data.json. */
export function resetMockPeople(): void {
  memory = clone(seed as Db);
  save();
}

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => window.setTimeout(() => resolve(clone(value)), LATENCY_MS));
}

function nextId(rows: { id: number }[]): number {
  return rows.reduce((max, row) => Math.max(max, row.id), 0) + 1;
}

function now(): string {
  return new Date().toISOString();
}

function today(): string {
  return now().slice(0, 10);
}

// ---------- Errors and validation ----------

type FieldErrors = Record<string, string>;

function failIfAny(errors: FieldErrors): void {
  if (Object.keys(errors).length) throw new AcademicApiError(422, "Check the highlighted fields.", errors);
}

function invalid(field: string, message: string): never {
  throw new AcademicApiError(422, "Check the highlighted fields.", { [field]: message });
}

function conflict(message: string): never {
  throw new AcademicApiError(409, message);
}

function notFound(label: string): never {
  throw new AcademicApiError(404, `${label} not found`);
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MOBILE = /^\+?[0-9][0-9\s-]{6,18}$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

function clean(value: string | null | undefined): string {
  return (value ?? "").trim();
}

function optional(value: string | null | undefined): string | null {
  const text = clean(value);
  return text ? text : null;
}

function same(a: string | null | undefined, b: string | null | undefined): boolean {
  return clean(a).toLowerCase() === clean(b).toLowerCase();
}

function digits(value: string | null | undefined): string {
  return clean(value).replace(/\D/g, "");
}

function matches(q: string | undefined, ...values: (string | null | undefined)[]): boolean {
  const needle = clean(q).toLowerCase();
  return !needle || values.some((value) => (value ?? "").toLowerCase().includes(needle));
}

function statusMatches(status: number, filter?: string): boolean {
  return filter !== "0" && filter !== "1" ? true : String(status) === filter;
}

function isDate(value: string | null | undefined): value is string {
  if (!value || !DATE.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function yearsBetween(from: string, to: string): number {
  const a = new Date(`${from}T00:00:00Z`);
  const b = new Date(`${to}T00:00:00Z`);
  let years = b.getUTCFullYear() - a.getUTCFullYear();
  if (b.getUTCMonth() < a.getUTCMonth() || (b.getUTCMonth() === a.getUTCMonth() && b.getUTCDate() < a.getUTCDate())) years -= 1;
  return years;
}

function checkName(errors: FieldErrors, prefix: string, first: string, last: string) {
  if (!clean(first)) errors[`${prefix}first_name`] = "First name is required";
  else if (clean(first).length > 128) errors[`${prefix}first_name`] = "First name must be 128 characters or fewer";
  if (!clean(last)) errors[`${prefix}last_name`] = "Last name is required";
  else if (clean(last).length > 128) errors[`${prefix}last_name`] = "Last name must be 128 characters or fewer";
}

function checkEmail(errors: FieldErrors, field: string, value: string | null | undefined, required: boolean) {
  const email = clean(value);
  if (!email) {
    if (required) errors[field] = "Email is required";
  } else if (!EMAIL.test(email)) errors[field] = "Enter a valid email address";
}

function checkMobile(errors: FieldErrors, field: string, value: string | null | undefined, required: boolean) {
  const mobile = clean(value);
  if (!mobile) {
    if (required) errors[field] = "Phone number is required";
  } else if (!MOBILE.test(mobile) || digits(mobile).length < 7 || digits(mobile).length > 15) {
    errors[field] = "Enter a valid phone number (7 to 15 digits)";
  }
}

function asStatus(value: unknown): RecordStatus {
  return value === 0 ? 0 : 1;
}

function paginate<T>(rows: T[], pageNumber = 1, pageSize = 20): Page<T> {
  const size = Math.min(Math.max(pageSize, 1), 50);
  const lastPage = Math.max(1, Math.ceil(rows.length / size));
  const current = Math.min(Math.max(pageNumber, 1), lastPage);
  return { items: rows.slice((current - 1) * size, current * size), total: rows.length, page: current, page_size: size };
}

function fullName(row: { first_name: string; last_name: string }): string {
  return `${row.first_name} ${row.last_name}`.trim();
}

// ---------- Academic lookups ----------

type Placement = { session_name: string; class_id: number; class_name: string; section_name: string };

function placement(sessionYearId: number, classSectionId: number): Placement {
  const academic = mockAcademicSnapshot();
  const session = academic.sessions.find((row) => row.id === sessionYearId);
  const classSection = academic.class_sections.find((row) => row.id === classSectionId);
  const schoolClass = academic.classes.find((row) => row.id === classSection?.class_id);
  const section = academic.sections.find((row) => row.id === classSection?.section_id);
  return {
    session_name: session?.name ?? "—",
    class_id: schoolClass?.id ?? 0,
    class_name: schoolClass?.name ?? "—",
    section_name: section?.name ?? "—",
  };
}

/** The same academic checks the live API runs on a student's session and section. */
function checkPlacement(errors: FieldErrors, sessionYearId: number, classSectionId: number, current?: StudentRecord) {
  const academic = mockAcademicSnapshot();
  const session = academic.sessions.find((row) => row.id === sessionYearId);
  if (!session) errors.session_year_id = "Choose an academic session";
  const classSection = academic.class_sections.find((row) => row.id === classSectionId);
  if (!classSection) {
    errors.class_section_id = "Choose a section";
    return;
  }
  const schoolClass = academic.classes.find((row) => row.id === classSection.class_id);
  const unchanged = current && current.class_section_id === classSectionId && current.session_year_id === sessionYearId;
  if (unchanged) return;
  if (!schoolClass || schoolClass.status !== 1) errors.class_section_id = "This class is inactive";
  else if (classSection.status !== 1) errors.class_section_id = "This section is inactive";
  else if (session && schoolClass.session_year_id !== null && schoolClass.session_year_id !== session.id) {
    errors.class_section_id = `${schoolClass.name} doesn't run in the ${session.name} session`;
  }
}

// ---------- Ownership ----------

function ownStudent(id: number): StudentRecord {
  const row = db().students.find((item) => item.id === id && item.school_id === db().school_id);
  return row ?? notFound("Student");
}

function ownParent(id: number): ParentRecord {
  const row = db().parents.find((item) => item.id === id && item.school_id === db().school_id);
  return row ?? notFound("Parent");
}

function ownEmployee(kind: EmployeeKind, id: number): EmployeeRecord {
  const row = db().employees.find((item) => item.id === id && item.kind === kind && item.school_id === db().school_id);
  return row ?? notFound(kind === "teachers" ? "Teacher" : "Staff member");
}

/** Every person in the school shares one email namespace, like the `users` table. */
function emailTaken(email: string, except?: { table: "students" | "parents" | "employees"; id: number }): string | null {
  const data = db();
  const hit = (table: "students" | "parents" | "employees", rows: { id: number; school_id: number; email: string | null }[]) =>
    rows.some((row) => row.school_id === data.school_id && row.email && same(row.email, email) && !(except?.table === table && except.id === row.id));
  if (hit("parents", data.parents)) return "a parent";
  if (hit("employees", data.employees)) return "a teacher or staff member";
  if (hit("students", data.students)) return "a student";
  return null;
}

// ---------- Students ----------

function linksFor(studentId: number): LinkRecord[] {
  return db().guardian_links.filter((link) => link.student_id === studentId);
}

function guardianLinks(studentId: number): GuardianLink[] {
  return linksFor(studentId)
    .map((link): GuardianLink | null => {
      const parent = db().parents.find((row) => row.id === link.parent_id);
      return parent
        ? {
            parent_id: parent.id,
            name: fullName(parent),
            email: parent.email,
            mobile: parent.mobile,
            relationship: link.relationship as Relationship,
            is_primary: link.is_primary,
          }
        : null;
    })
    .filter((link): link is GuardianLink => link !== null)
    .sort((a, b) => Number(b.is_primary) - Number(a.is_primary) || a.name.localeCompare(b.name));
}

function studentRow(row: StudentRecord): StudentRow {
  const place = placement(row.session_year_id, row.class_section_id);
  const primary = guardianLinks(row.id)[0];
  return {
    id: row.id,
    admission_no: row.admission_no,
    first_name: row.first_name,
    last_name: row.last_name,
    name: fullName(row),
    session_year_id: row.session_year_id,
    session_name: place.session_name,
    class_id: place.class_id,
    class_name: place.class_name,
    class_section_id: row.class_section_id,
    section_name: place.section_name,
    roll_number: row.roll_number,
    guardian_name: primary?.name ?? null,
    guardian_mobile: primary?.mobile ?? null,
    admission_date: row.admission_date,
    photo_url: row.photo_url,
    status: asStatus(row.status),
  };
}

function studentDetail(row: StudentRecord): Student {
  return {
    ...studentRow(row),
    dob: row.dob,
    gender: row.gender as Gender,
    email: row.email,
    mobile: row.mobile,
    current_address: row.current_address,
    permanent_address: row.permanent_address,
    guardians: guardianLinks(row.id),
    documents: row.documents,
  };
}

function nextAdmissionNo(admissionDate: string): string {
  const year = admissionDate.slice(0, 4);
  const prefix = `ADM${year}`;
  const used = db()
    .students.filter((row) => row.school_id === db().school_id && row.admission_no.startsWith(prefix))
    .map((row) => Number(row.admission_no.slice(prefix.length)) || 0);
  return `${prefix}${String(Math.max(0, ...used) + 1).padStart(4, "0")}`;
}

function validateStudent(input: StudentInput, errors: FieldErrors, current?: StudentRecord) {
  checkName(errors, "", input.first_name, input.last_name);
  if (!isDate(input.dob)) errors.dob = "Enter the date of birth";
  else if (input.dob > today()) errors.dob = "Date of birth can't be in the future";
  else {
    const age = yearsBetween(input.dob, today());
    if (age < 2 || age > 30) errors.dob = "Students must be between 2 and 30 years old";
  }
  if (!GENDERS.some((gender) => gender.value === input.gender)) errors.gender = "Choose a gender";
  if (!isDate(input.admission_date)) errors.admission_date = "Enter the admission date";
  else if (isDate(input.dob) && input.admission_date <= input.dob) errors.admission_date = "Admission date must be after the date of birth";
  checkPlacement(errors, Number(input.session_year_id), Number(input.class_section_id), current);
  const admissionNo = clean(input.admission_no);
  if (admissionNo.length > 32) errors.admission_no = "Admission number must be 32 characters or fewer";
  else if (admissionNo && !/^[A-Za-z0-9/-]+$/.test(admissionNo)) errors.admission_no = "Use letters, numbers, - and / only";
  if (current && !admissionNo) errors.admission_no = "Admission number is required";
  if (input.roll_number !== null && input.roll_number !== undefined && (!Number.isInteger(input.roll_number) || input.roll_number < 1 || input.roll_number > 9999)) {
    errors.roll_number = "Roll number must be a whole number from 1 to 9999";
  }
  checkEmail(errors, "email", input.email, false);
  checkMobile(errors, "mobile", input.mobile, false);
  if (!clean(input.current_address)) errors.current_address = "Address is required";
  else if (clean(input.current_address).length > 512) errors.current_address = "Address must be 512 characters or fewer";
  if (clean(input.permanent_address).length > 512) errors.permanent_address = "Address must be 512 characters or fewer";
}

function checkStudentConflicts(input: StudentInput, admissionNo: string, current?: StudentRecord) {
  const data = db();
  const others = data.students.filter((row) => row.school_id === data.school_id && row.id !== current?.id);
  const sameNo = others.find((row) => same(row.admission_no, admissionNo));
  if (sameNo) conflict(`Admission number ${admissionNo} is already used by ${fullName(sameNo)}`);
  if (input.roll_number) {
    const sameRoll = others.find(
      (row) => row.session_year_id === Number(input.session_year_id) && row.class_section_id === Number(input.class_section_id) && row.roll_number === input.roll_number,
    );
    if (sameRoll) conflict(`Roll number ${input.roll_number} is already used by ${fullName(sameRoll)} in this section`);
  }
  const email = optional(input.email);
  if (email) {
    const owner = emailTaken(email, current ? { table: "students", id: current.id } : undefined);
    if (owner) conflict(`${email} is already used by ${owner} in this school`);
  }
}

function validateNewGuardian(choice: GuardianChoice, errors: FieldErrors) {
  if (!RELATIONSHIPS.includes(choice.relationship)) errors["guardian.relationship"] = "Choose the relationship";
  if ("parent_id" in choice) {
    const parent = db().parents.find((row) => row.id === Number(choice.parent_id) && row.school_id === db().school_id);
    if (!parent) errors["guardian.parent_id"] = "Choose a parent from this school";
    return;
  }
  checkName(errors, "guardian.", choice.first_name, choice.last_name);
  checkEmail(errors, "guardian.email", choice.email, true);
  checkMobile(errors, "guardian.mobile", choice.mobile, true);
}

function duplicateParent(email: string, mobile: string, exceptId?: number): ParentRecord | undefined {
  return db().parents.find(
    (row) =>
      row.school_id === db().school_id &&
      row.id !== exceptId &&
      ((email && same(row.email, email)) || (digits(mobile) && digits(row.mobile) === digits(mobile))),
  );
}

function setPrimary(studentId: number, parentId: number) {
  for (const link of linksFor(studentId)) link.is_primary = link.parent_id === parentId;
}

// ---------- Parents ----------

function childLinks(parentId: number): ChildLink[] {
  return db()
    .guardian_links.filter((link) => link.parent_id === parentId)
    .map((link): ChildLink | null => {
      const student = db().students.find((row) => row.id === link.student_id && row.school_id === db().school_id);
      if (!student) return null;
      const place = placement(student.session_year_id, student.class_section_id);
      return {
        student_id: student.id,
        name: fullName(student),
        admission_no: student.admission_no,
        class_name: place.class_name,
        section_name: place.section_name,
        relationship: link.relationship as Relationship,
        is_primary: link.is_primary,
        status: asStatus(student.status),
      };
    })
    .filter((link): link is ChildLink => link !== null)
    .sort((a, b) => a.name.localeCompare(b.name));
}

function parentDetail(row: ParentRecord): Parent {
  return {
    id: row.id,
    first_name: row.first_name,
    last_name: row.last_name,
    name: fullName(row),
    email: row.email,
    mobile: row.mobile,
    current_address: row.current_address,
    occupation: row.occupation,
    status: asStatus(row.status),
    children: childLinks(row.id),
  };
}

function validateParent(input: ParentInput, errors: FieldErrors) {
  checkName(errors, "", input.first_name, input.last_name);
  checkEmail(errors, "email", input.email, true);
  checkMobile(errors, "mobile", input.mobile, true);
  if (clean(input.current_address).length > 512) errors.current_address = "Address must be 512 characters or fewer";
  if (clean(input.occupation).length > 255) errors.occupation = "Occupation must be 255 characters or fewer";
}

function checkParentConflicts(input: ParentInput, exceptId?: number) {
  const duplicate = duplicateParent(clean(input.email), clean(input.mobile), exceptId);
  if (duplicate) {
    const field = same(duplicate.email, input.email) ? `email ${clean(input.email)}` : `phone number ${clean(input.mobile)}`;
    conflict(`${fullName(duplicate)} already has the ${field}. Open their profile and link the student there instead of adding a new parent.`);
  }
  const owner = emailTaken(clean(input.email), exceptId ? { table: "parents", id: exceptId } : undefined);
  if (owner && owner !== "a parent") conflict(`${clean(input.email)} is already used by ${owner} in this school`);
}

// ---------- Employees ----------

function employeeRow(row: EmployeeRecord): EmployeeRow {
  return {
    id: row.id,
    employee_code: row.employee_code,
    first_name: row.first_name,
    last_name: row.last_name,
    name: fullName(row),
    email: row.email,
    mobile: row.mobile,
    department: row.department,
    designation: row.designation,
    joining_date: row.joining_date,
    employment_type: row.employment_type as EmploymentType,
    photo_url: row.photo_url,
    status: asStatus(row.status),
  };
}

function employeeDetail(row: EmployeeRecord): Employee {
  return {
    ...employeeRow(row),
    gender: (row.gender as Gender | null) ?? null,
    dob: row.dob,
    qualification: row.qualification,
    current_address: row.current_address,
    documents: row.documents,
  };
}

function nextEmployeeCode(kind: EmployeeKind): string {
  const prefix = kind === "teachers" ? "TCH" : "STF";
  const used = db()
    .employees.filter((row) => row.school_id === db().school_id && row.employee_code.startsWith(prefix))
    .map((row) => Number(row.employee_code.slice(prefix.length)) || 0);
  return `${prefix}${String(Math.max(0, ...used) + 1).padStart(4, "0")}`;
}

function validateEmployee(kind: EmployeeKind, input: EmployeeInput, errors: FieldErrors, current?: EmployeeRecord) {
  checkName(errors, "", input.first_name, input.last_name);
  checkEmail(errors, "email", input.email, true);
  checkMobile(errors, "mobile", input.mobile, true);
  const code = clean(input.employee_code);
  if (current && !code) errors.employee_code = "Employee ID is required";
  else if (code.length > 32) errors.employee_code = "Employee ID must be 32 characters or fewer";
  else if (code && !/^[A-Za-z0-9/-]+$/.test(code)) errors.employee_code = "Use letters, numbers, - and / only";
  if (!clean(input.department)) errors.department = "Department is required";
  if (!clean(input.designation)) errors.designation = "Designation is required";
  if (kind === "teachers" && !clean(input.qualification)) errors.qualification = "Qualification is required for teachers";
  if (!isDate(input.joining_date)) errors.joining_date = "Enter the joining date";
  if (!EMPLOYMENT_TYPES.includes(input.employment_type)) errors.employment_type = "Choose the employment type";
  if (input.gender && !GENDERS.some((gender) => gender.value === input.gender)) errors.gender = "Choose a gender";
  if (input.dob) {
    if (!isDate(input.dob)) errors.dob = "Enter a valid date of birth";
    else if (yearsBetween(input.dob, today()) < 18) errors.dob = "Employees must be at least 18 years old";
    else if (isDate(input.joining_date) && input.joining_date <= input.dob) errors.joining_date = "Joining date must be after the date of birth";
  }
  if (clean(input.current_address).length > 512) errors.current_address = "Address must be 512 characters or fewer";
}

function checkEmployeeConflicts(kind: EmployeeKind, input: EmployeeInput, code: string, current?: EmployeeRecord) {
  const data = db();
  const sameCode = data.employees.find((row) => row.school_id === data.school_id && row.id !== current?.id && same(row.employee_code, code));
  if (sameCode) conflict(`Employee ID ${code} is already used by ${fullName(sameCode)}`);
  const owner = emailTaken(clean(input.email), current ? { table: "employees", id: current.id } : undefined);
  if (owner) conflict(`${clean(input.email)} is already used by ${owner} in this school`);
  void kind;
}

function applyEmployee(row: EmployeeRecord, input: EmployeeInput, code: string) {
  row.employee_code = code;
  row.first_name = clean(input.first_name);
  row.last_name = clean(input.last_name);
  row.email = clean(input.email).toLowerCase();
  row.mobile = clean(input.mobile);
  row.gender = input.gender || null;
  row.dob = input.dob || null;
  row.qualification = optional(input.qualification);
  row.department = clean(input.department);
  row.designation = clean(input.designation);
  row.joining_date = input.joining_date;
  row.employment_type = input.employment_type;
  row.current_address = optional(input.current_address);
  row.status = asStatus(input.status);
}

// ---------- Files ----------

function fileOwner(owner: FileOwner, id: number): { photo_url: string | null; documents?: StoredFile[] } {
  return owner === "students" ? ownStudent(id) : ownEmployee(owner, id);
}

function readFile(file: File): Promise<string | null> {
  if (file.size > PERSIST_FILE_BYTES) return Promise.resolve(URL.createObjectURL(file));
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : null);
    reader.onerror = () => resolve(null);
    reader.readAsDataURL(file);
  });
}

// ---------- Service ----------

export const mockPeopleService: PeopleService = {
  async listStudents(query: StudentQuery = {}) {
    const data = db();
    let rows = data.students
      .filter((row) => row.school_id === data.school_id)
      .map((row) => ({ row, view: studentRow(row) }))
      .filter(({ row, view }) => statusMatches(row.status, query.status))
      .filter(({ view }) => !query.sessionYearId || view.session_year_id === query.sessionYearId)
      .filter(({ view }) => !query.classId || view.class_id === query.classId)
      .filter(({ view }) => !query.classSectionId || view.class_section_id === query.classSectionId)
      .filter(({ row }) => !query.parentId || linksFor(row.id).some((link) => link.parent_id === query.parentId))
      .filter(({ view }) => matches(query.q, view.name, view.admission_no));
    const order = query.order === "desc" ? -1 : 1;
    const key = (view: StudentRow): string => {
      switch (query.sort) {
        case "admission_no":
          return view.admission_no;
        case "admission_date":
          return view.admission_date;
        case "class":
          return `${view.class_name.padStart(12, " ")} ${view.section_name}`;
        default:
          return view.name.toLowerCase();
      }
    };
    rows = rows.sort((a, b) => key(a.view).localeCompare(key(b.view), undefined, { numeric: true }) * order || a.view.id - b.view.id);
    return delay(paginate(rows.map(({ view }) => view), query.page, query.pageSize));
  },

  async getStudent(id) {
    return delay(studentDetail(ownStudent(id)));
  },

  async createStudent(input: StudentCreateInput) {
    const errors: FieldErrors = {};
    validateStudent(input, errors);
    if (!input.guardian) errors["guardian.parent_id"] = "Choose or add a parent or guardian";
    else validateNewGuardian(input.guardian, errors);
    failIfAny(errors);

    const data = db();
    const admissionNo = clean(input.admission_no) || nextAdmissionNo(input.admission_date);
    checkStudentConflicts(input, admissionNo);

    let parentId: number;
    if ("parent_id" in input.guardian) {
      parentId = Number(input.guardian.parent_id);
    } else {
      const guardian = input.guardian;
      const duplicate = duplicateParent(clean(guardian.email), clean(guardian.mobile));
      if (duplicate) {
        throw new AcademicApiError(409, `${fullName(duplicate)} is already registered with this email or phone number. Choose them as an existing parent instead.`);
      }
      const owner = emailTaken(clean(guardian.email));
      if (owner) conflict(`${clean(guardian.email)} is already used by ${owner} in this school`);
      parentId = nextId(data.parents);
      data.parents.push({
        id: parentId,
        school_id: data.school_id,
        first_name: clean(guardian.first_name),
        last_name: clean(guardian.last_name),
        email: clean(guardian.email).toLowerCase(),
        mobile: clean(guardian.mobile),
        current_address: clean(input.current_address),
        occupation: null,
        status: 1,
      });
    }

    const row: StudentRecord = {
      id: nextId(data.students),
      school_id: data.school_id,
      admission_no: admissionNo,
      first_name: clean(input.first_name),
      last_name: clean(input.last_name),
      dob: input.dob,
      gender: input.gender,
      email: optional(input.email)?.toLowerCase() ?? null,
      mobile: optional(input.mobile),
      current_address: clean(input.current_address),
      permanent_address: optional(input.permanent_address),
      session_year_id: Number(input.session_year_id),
      class_section_id: Number(input.class_section_id),
      roll_number: input.roll_number ?? null,
      admission_date: input.admission_date,
      status: asStatus(input.status),
      photo_url: null,
      documents: [],
    };
    data.students.push(row);
    data.guardian_links.push({ student_id: row.id, parent_id: parentId, relationship: input.guardian.relationship, is_primary: true });
    save();
    return delay(studentDetail(row));
  },

  async updateStudent(id, input: StudentInput) {
    const row = ownStudent(id);
    const errors: FieldErrors = {};
    validateStudent(input, errors, row);
    failIfAny(errors);
    const admissionNo = clean(input.admission_no);
    checkStudentConflicts(input, admissionNo, row);
    Object.assign(row, {
      admission_no: admissionNo,
      first_name: clean(input.first_name),
      last_name: clean(input.last_name),
      dob: input.dob,
      gender: input.gender,
      email: optional(input.email)?.toLowerCase() ?? null,
      mobile: optional(input.mobile),
      current_address: clean(input.current_address),
      permanent_address: optional(input.permanent_address),
      session_year_id: Number(input.session_year_id),
      class_section_id: Number(input.class_section_id),
      roll_number: input.roll_number ?? null,
      admission_date: input.admission_date,
      status: asStatus(input.status),
    });
    save();
    return delay(studentDetail(row));
  },

  async setStudentStatus(id, status) {
    const row = ownStudent(id);
    row.status = asStatus(status);
    save();
    return delay(studentDetail(row));
  },

  async linkGuardian(studentId, link) {
    const student = ownStudent(studentId);
    const parent = db().parents.find((row) => row.id === Number(link.parent_id) && row.school_id === db().school_id);
    if (!parent) invalid("parent_id", "Choose a parent from this school");
    if (!RELATIONSHIPS.includes(link.relationship)) invalid("relationship", "Choose the relationship");
    const existing = linksFor(student.id);
    if (existing.some((item) => item.parent_id === parent.id)) conflict(`${fullName(parent)} is already linked to ${fullName(student)}`);
    if (existing.length >= 4) conflict(`${fullName(student)} already has 4 guardians. Remove one before adding another.`);
    db().guardian_links.push({ student_id: student.id, parent_id: parent.id, relationship: link.relationship, is_primary: existing.length === 0 });
    if (link.is_primary) setPrimary(student.id, parent.id);
    save();
    return delay(studentDetail(student));
  },

  async unlinkGuardian(studentId, parentId) {
    const student = ownStudent(studentId);
    const links = linksFor(student.id);
    const link = links.find((item) => item.parent_id === parentId);
    if (!link) notFound("Guardian link");
    if (links.length === 1) conflict(`${fullName(student)} must keep at least one parent or guardian. Link another one first.`);
    db().guardian_links = db().guardian_links.filter((item) => item !== link);
    if (link.is_primary) {
      const next = linksFor(student.id)[0];
      if (next) next.is_primary = true;
    }
    save();
    return delay(studentDetail(student));
  },

  async listParents(query: ParentQuery = {}) {
    const data = db();
    const rows = data.parents
      .filter((row) => row.school_id === data.school_id)
      .filter((row) => statusMatches(row.status, query.status))
      .filter((row) => !clean(query.email) || same(row.email, query.email))
      .filter((row) => !digits(query.mobile) || digits(row.mobile) === digits(query.mobile))
      .filter((row) => matches(query.q, fullName(row), row.email, row.mobile))
      .sort((a, b) => fullName(a).localeCompare(fullName(b)))
      .map(parentDetail);
    return delay(paginate(rows, query.page, query.pageSize));
  },

  async getParent(id) {
    return delay(parentDetail(ownParent(id)));
  },

  async createParent(input: ParentCreateInput) {
    const errors: FieldErrors = {};
    validateParent(input, errors);
    const students = input.students ?? [];
    students.forEach((link, index) => {
      if (!db().students.some((row) => row.id === Number(link.student_id) && row.school_id === db().school_id)) {
        errors[`students.${index}.student_id`] = "Choose a student from this school";
        errors.students = "Choose students from this school";
      }
      if (!RELATIONSHIPS.includes(link.relationship)) errors.students = "Choose the relationship for each student";
    });
    if (new Set(students.map((link) => link.student_id)).size !== students.length) errors.students = "Each student can be linked once";
    failIfAny(errors);
    checkParentConflicts(input);
    const data = db();
    const row: ParentRecord = {
      id: nextId(data.parents),
      school_id: data.school_id,
      first_name: clean(input.first_name),
      last_name: clean(input.last_name),
      email: clean(input.email).toLowerCase(),
      mobile: clean(input.mobile),
      current_address: optional(input.current_address),
      occupation: optional(input.occupation),
      status: asStatus(input.status),
    };
    data.parents.push(row);
    for (const link of students) {
      const already = linksFor(Number(link.student_id));
      if (already.length >= 4) conflict("A student can have at most 4 guardians.");
      data.guardian_links.push({ student_id: Number(link.student_id), parent_id: row.id, relationship: link.relationship, is_primary: already.length === 0 });
    }
    save();
    return delay(parentDetail(row));
  },

  async updateParent(id, input: ParentInput) {
    const row = ownParent(id);
    const errors: FieldErrors = {};
    validateParent(input, errors);
    failIfAny(errors);
    checkParentConflicts(input, row.id);
    Object.assign(row, {
      first_name: clean(input.first_name),
      last_name: clean(input.last_name),
      email: clean(input.email).toLowerCase(),
      mobile: clean(input.mobile),
      current_address: optional(input.current_address),
      occupation: optional(input.occupation),
      status: asStatus(input.status),
    });
    save();
    return delay(parentDetail(row));
  },

  async setParentStatus(id, status) {
    const row = ownParent(id);
    row.status = asStatus(status);
    save();
    return delay(parentDetail(row));
  },

  async listEmployees(kind: EmployeeKind, query: EmployeeQuery = {}) {
    const data = db();
    const rows = data.employees
      .filter((row) => row.school_id === data.school_id && row.kind === kind)
      .filter((row) => statusMatches(row.status, query.status))
      .filter((row) => !query.department || same(row.department, query.department))
      .filter((row) => !query.employmentType || row.employment_type === query.employmentType)
      .filter((row) => matches(query.q, fullName(row), row.employee_code, row.email, row.mobile, row.designation))
      .sort((a, b) => fullName(a).localeCompare(fullName(b)))
      .map(employeeRow);
    return delay(paginate(rows, query.page, query.pageSize));
  },

  async listDepartments(kind) {
    const data = db();
    const names = new Set(data.employees.filter((row) => row.school_id === data.school_id && row.kind === kind).map((row) => row.department));
    return delay([...names].sort());
  },

  async getEmployee(kind, id) {
    return delay(employeeDetail(ownEmployee(kind, id)));
  },

  async createEmployee(kind, input) {
    const errors: FieldErrors = {};
    validateEmployee(kind, input, errors);
    failIfAny(errors);
    const code = clean(input.employee_code) || nextEmployeeCode(kind);
    checkEmployeeConflicts(kind, input, code);
    const data = db();
    const row = {
      id: Math.max(nextId(data.employees), kind === "teachers" ? 101 : 201),
      school_id: data.school_id,
      kind,
      photo_url: null,
      documents: [],
    } as unknown as EmployeeRecord;
    applyEmployee(row, input, code);
    data.employees.push(row);
    save();
    return delay(employeeDetail(row));
  },

  async updateEmployee(kind, id, input) {
    const row = ownEmployee(kind, id);
    const errors: FieldErrors = {};
    validateEmployee(kind, input, errors, row);
    failIfAny(errors);
    const code = clean(input.employee_code);
    checkEmployeeConflicts(kind, input, code, row);
    applyEmployee(row, input, code);
    save();
    return delay(employeeDetail(row));
  },

  async setEmployeeStatus(kind, id, status) {
    const row = ownEmployee(kind, id);
    row.status = asStatus(status);
    save();
    return delay(employeeDetail(row));
  },

  async uploadPhoto(owner, id, file) {
    const record = fileOwner(owner, id);
    const problem = photoProblem(file);
    if (problem) invalid("file", problem);
    record.photo_url = await readFile(file);
    save();
    return delay({ photo_url: record.photo_url });
  },

  async uploadDocument(owner, id, file, title) {
    const record = fileOwner(owner, id);
    const problem = documentProblem(file);
    if (problem) invalid("file", problem);
    const documents = (record.documents ??= []);
    if (documents.length >= DOCUMENTS_PER_RECORD) conflict(`A record can hold up to ${DOCUMENTS_PER_RECORD} documents. Remove one first.`);
    const stored: StoredFile = {
      id: db().next_file_id++,
      title: clean(title).slice(0, 120) || file.name,
      file_name: file.name,
      content_type: fileType(file),
      size: file.size,
      url: await readFile(file),
      uploaded_at: now(),
    };
    documents.push(stored);
    save();
    return delay(stored);
  },

  async deleteDocument(owner, id, documentId) {
    const record = fileOwner(owner, id);
    const documents = record.documents ?? [];
    const index = documents.findIndex((item) => item.id === documentId);
    if (index < 0) notFound("Document");
    documents.splice(index, 1);
    save();
    await delay(null);
  },
};
