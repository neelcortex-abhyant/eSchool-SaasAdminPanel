/**
 * Shapes shared by the live people client and the mock client.
 * The live contract is in backend/docs/PEOPLE_API_CONTRACT.md.
 */
import type { Page, RecordStatus } from "@/lib/academics/types";

export type { Page, RecordStatus };

export type Gender = "male" | "female" | "other";
export const GENDERS: { value: Gender; label: string }[] = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "other", label: "Other" },
];

export type Relationship = "Father" | "Mother" | "Guardian" | "Grandparent" | "Sibling" | "Other";
export const RELATIONSHIPS: Relationship[] = ["Father", "Mother", "Guardian", "Grandparent", "Sibling", "Other"];

export type SortOrder = "asc" | "desc";

/** A photo or document stored by the backend for one person. */
export type StoredFile = {
  id: number;
  title: string;
  file_name: string;
  content_type: string;
  size: number;
  /** A short-lived link the browser can open. Null when the file can't be previewed. */
  url: string | null;
  uploaded_at: string;
};

/** Which kind of record an upload belongs to. */
export type FileOwner = "students" | "teachers" | "staff";

// ---------- Students ----------

export type GuardianLink = {
  parent_id: number;
  name: string;
  email: string | null;
  mobile: string | null;
  relationship: Relationship;
  is_primary: boolean;
};

export type StudentRow = {
  id: number;
  admission_no: string;
  first_name: string;
  last_name: string;
  name: string;
  session_year_id: number;
  session_name: string;
  class_id: number;
  class_name: string;
  class_section_id: number;
  section_name: string;
  roll_number: number | null;
  /** The primary guardian, shown in the listing. */
  guardian_name: string | null;
  guardian_mobile: string | null;
  admission_date: string;
  photo_url: string | null;
  status: RecordStatus;
};

export type Student = StudentRow & {
  dob: string;
  gender: Gender;
  email: string | null;
  mobile: string | null;
  current_address: string;
  permanent_address: string | null;
  guardians: GuardianLink[];
  documents: StoredFile[];
};

/** Either an existing parent's id, or the details of a new parent to create with the student. */
export type GuardianChoice =
  | { parent_id: number; relationship: Relationship }
  | { first_name: string; last_name: string; email: string; mobile: string; relationship: Relationship };

export type StudentInput = {
  first_name: string;
  last_name: string;
  dob: string;
  gender: Gender;
  /** Leave empty on create to let the server generate the next number. */
  admission_no?: string;
  admission_date: string;
  session_year_id: number;
  class_section_id: number;
  roll_number?: number | null;
  email?: string | null;
  mobile?: string | null;
  current_address: string;
  permanent_address?: string | null;
  status: RecordStatus;
};

export type StudentCreateInput = StudentInput & { guardian: GuardianChoice };

export type StudentSort = "name" | "admission_no" | "admission_date" | "class";

export type StudentQuery = {
  page?: number;
  pageSize?: number;
  q?: string;
  status?: "" | "0" | "1";
  sessionYearId?: number | "";
  classId?: number | "";
  classSectionId?: number | "";
  /** Exact match, used to find the students linked to one parent. */
  parentId?: number | "";
  sort?: StudentSort;
  order?: SortOrder;
};

// ---------- Parents ----------

export type ChildLink = {
  student_id: number;
  name: string;
  admission_no: string;
  class_name: string;
  section_name: string;
  relationship: Relationship;
  is_primary: boolean;
  status: RecordStatus;
};

export type Parent = {
  id: number;
  first_name: string;
  last_name: string;
  name: string;
  email: string;
  mobile: string;
  current_address: string | null;
  occupation: string | null;
  status: RecordStatus;
  children: ChildLink[];
};

export type ParentInput = {
  first_name: string;
  last_name: string;
  email: string;
  mobile: string;
  current_address?: string | null;
  occupation?: string | null;
  status: RecordStatus;
};

export type StudentLinkInput = { student_id: number; relationship: Relationship };

export type ParentCreateInput = ParentInput & { students: StudentLinkInput[] };

export type ParentQuery = {
  page?: number;
  pageSize?: number;
  q?: string;
  status?: "" | "0" | "1";
  /** Exact, case-insensitive match. Used to warn about a duplicate before saving. */
  email?: string;
  mobile?: string;
};

// ---------- Teachers and staff ----------

/** Teachers and non-teaching staff share one record shape. */
export type EmployeeKind = "teachers" | "staff";

/**
 * Employment type (sample data: Permanent, Probation, Contract, Part-time) or the live
 * backend's employment status (active, on_leave, resigned, terminated). The choices offered
 * come from peopleSupport().employmentOptions.
 */
export type EmploymentType = string;
export const EMPLOYMENT_TYPES: EmploymentType[] = ["Permanent", "Probation", "Contract", "Part-time"];
/** The live backend's Staff.employment_status values. */
export const EMPLOYMENT_STATUSES: { value: string; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "on_leave", label: "On leave" },
  { value: "resigned", label: "Resigned" },
  { value: "terminated", label: "Terminated" },
];

export type EmployeeRow = {
  id: number;
  employee_code: string;
  first_name: string;
  last_name: string;
  name: string;
  email: string;
  mobile: string;
  department: string;
  designation: string;
  joining_date: string;
  employment_type: EmploymentType;
  photo_url: string | null;
  status: RecordStatus;
};

export type Employee = EmployeeRow & {
  gender: Gender | null;
  dob: string | null;
  qualification: string | null;
  current_address: string | null;
  documents: StoredFile[];
};

export type EmployeeInput = {
  /** Leave empty on create to let the server generate the next code. */
  employee_code?: string;
  first_name: string;
  last_name: string;
  email: string;
  mobile: string;
  gender?: Gender | null;
  dob?: string | null;
  qualification?: string | null;
  department: string;
  designation: string;
  joining_date: string;
  employment_type: EmploymentType;
  current_address?: string | null;
  /** Initial sign-in password, required by the live backend when adding a teacher or staff member. */
  password?: string;
  status: RecordStatus;
};

export type EmployeeQuery = {
  page?: number;
  pageSize?: number;
  q?: string;
  status?: "" | "0" | "1";
  department?: string;
  employmentType?: EmploymentType | "";
};

// ---------- Service ----------

export interface PeopleService {
  listStudents(query?: StudentQuery): Promise<Page<StudentRow>>;
  getStudent(id: number): Promise<Student>;
  createStudent(input: StudentCreateInput): Promise<Student>;
  updateStudent(id: number, input: StudentInput): Promise<Student>;
  setStudentStatus(id: number, status: RecordStatus): Promise<Student>;
  linkGuardian(studentId: number, link: { parent_id: number; relationship: Relationship; is_primary?: boolean }): Promise<Student>;
  unlinkGuardian(studentId: number, parentId: number): Promise<Student>;

  listParents(query?: ParentQuery): Promise<Page<Parent>>;
  getParent(id: number): Promise<Parent>;
  createParent(input: ParentCreateInput): Promise<Parent>;
  updateParent(id: number, input: ParentInput): Promise<Parent>;
  setParentStatus(id: number, status: RecordStatus): Promise<Parent>;

  listEmployees(kind: EmployeeKind, query?: EmployeeQuery): Promise<Page<EmployeeRow>>;
  listDepartments(kind: EmployeeKind): Promise<string[]>;
  getEmployee(kind: EmployeeKind, id: number): Promise<Employee>;
  createEmployee(kind: EmployeeKind, input: EmployeeInput): Promise<Employee>;
  updateEmployee(kind: EmployeeKind, id: number, input: EmployeeInput): Promise<Employee>;
  setEmployeeStatus(kind: EmployeeKind, id: number, status: RecordStatus): Promise<Employee>;

  uploadPhoto(owner: FileOwner, id: number, file: File): Promise<{ photo_url: string | null }>;
  uploadDocument(owner: FileOwner, id: number, file: File, title: string): Promise<StoredFile>;
  deleteDocument(owner: FileOwner, id: number, documentId: number): Promise<void>;
}
