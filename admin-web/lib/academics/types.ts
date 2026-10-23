/**
 * Academic structure types used by the School Admin UI.
 * Every record belongs to the signed-in admin's school. The server picks the school
 * from the session, so none of these types carry a school_id.
 */

/** 1 active, 0 inactive. Same encoding as the rest of the v1 API. */
export type RecordStatus = 0 | 1;

export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export type ListQuery = {
  page?: number;
  pageSize?: number;
  q?: string;
  status?: "" | "0" | "1";
};

export type AcademicSession = {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  /** The school's current session. Exactly one session is active at a time. */
  is_active: boolean;
};

export type SessionInput = {
  name: string;
  start_date: string;
  end_date: string;
};

export type Medium = {
  id: number;
  name: string;
};

export type SchoolClass = {
  id: number;
  name: string;
  medium_id: number;
  medium_name: string;
  /** Null means the class is used in every session. */
  session_year_id: number | null;
  session_name: string;
  status: RecordStatus;
};

export type ClassInput = {
  name: string;
  medium_id: number;
  session_year_id: number | null;
  status: RecordStatus;
};

export type ClassQuery = ListQuery & {
  sessionYearId?: number | "";
  mediumId?: number | "";
};

/** A section of one class, such as "A" in "Class 5 A". */
export type ClassSection = {
  id: number;
  class_id: number;
  class_name: string;
  section_id: number;
  section_name: string;
  status: RecordStatus;
};

export type SectionInput = {
  class_id: number;
  section_name: string;
  status: RecordStatus;
};

export type SectionQuery = ListQuery & {
  classId?: number | "";
};

export type SubjectType = "Theory" | "Practical";
export type SubjectKind = "Compulsory" | "Elective";

export type ClassSubjectLink = {
  class_id: number;
  class_name: string;
  type: SubjectKind;
};

export type Subject = {
  id: number;
  name: string;
  code: string | null;
  type: SubjectType;
  medium_id: number;
  medium_name: string;
  classes: ClassSubjectLink[];
  status: RecordStatus;
};

export type SubjectInput = {
  name: string;
  code: string;
  type: SubjectType;
  medium_id: number;
  classes: { class_id: number; type: SubjectKind }[];
  status: RecordStatus;
};

export type SubjectQuery = ListQuery & {
  classId?: number | "";
  kind?: "" | SubjectKind;
  type?: "" | SubjectType;
};

export type Teacher = {
  id: number;
  name: string;
  email: string;
};

export type TeacherAssignment = {
  id: number;
  session_year_id: number;
  session_name: string;
  class_id: number;
  class_name: string;
  class_section_id: number;
  section_name: string;
  subject_id: number;
  subject_name: string;
  teacher_id: number;
  teacher_name: string;
};

export type AssignmentInput = {
  session_year_id: number;
  class_section_id: number;
  subject_id: number;
  teacher_id: number;
};

export type AssignmentQuery = ListQuery & {
  sessionYearId?: number | "";
  classId?: number | "";
  classSectionId?: number | "";
  subjectId?: number | "";
  teacherId?: number | "";
};

/** One service per page. The live client and the mock client both implement it. */
export interface AcademicsService {
  listSessions(query?: ListQuery): Promise<Page<AcademicSession>>;
  createSession(input: SessionInput): Promise<AcademicSession>;
  updateSession(id: number, input: SessionInput): Promise<AcademicSession>;
  activateSession(id: number): Promise<AcademicSession>;

  listMediums(): Promise<Medium[]>;
  createMedium(name: string): Promise<Medium>;
  updateMedium(id: number, name: string): Promise<Medium>;
  deleteMedium(id: number): Promise<void>;

  listClasses(query?: ClassQuery): Promise<Page<SchoolClass>>;
  createClass(input: ClassInput): Promise<SchoolClass>;
  updateClass(id: number, input: ClassInput): Promise<SchoolClass>;

  listSections(query?: SectionQuery): Promise<Page<ClassSection>>;
  createSection(input: SectionInput): Promise<ClassSection>;
  updateSection(id: number, input: SectionInput): Promise<ClassSection>;

  listSubjects(query?: SubjectQuery): Promise<Page<Subject>>;
  createSubject(input: SubjectInput): Promise<Subject>;
  updateSubject(id: number, input: SubjectInput): Promise<Subject>;

  listTeachers(q?: string): Promise<Teacher[]>;

  listAssignments(query?: AssignmentQuery): Promise<Page<TeacherAssignment>>;
  createAssignment(input: AssignmentInput): Promise<TeacherAssignment>;
  updateAssignment(id: number, input: AssignmentInput): Promise<TeacherAssignment>;
  deleteAssignment(id: number): Promise<void>;
}
