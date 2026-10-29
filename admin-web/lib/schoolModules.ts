export type SchoolField = {
  key: string;
  label: string;
  type?: "text" | "number" | "date" | "textarea";
  required?: boolean;
};

export type SchoolModule = {
  title: string;
  /** Path under the live `/api/admin` API. */
  endpoint: string;
  columns: { key: string; label: string }[];
  fields: SchoolField[];
};

/** Menu slugs that use a live admin resource. */
export const SCHOOL_MODULE_ALIAS: Record<string, string> = {
  subject: "subjects",
  class: "classes",
  "students-admission": "students",
  "student-details": "students",
  "student-attendance": "attendance",
  "month-wise-attendance": "attendance",
  "student-leave": "leaves",
  "staff-leave": "leaves",
  "manage-offline-exam": "exams",
  announcement: "notices",
  "fees-type": "fees",
  "manage-fees": "fees",
  "manage-expense": "expenses",
  "expense-report": "expenses",
  "student-reports": "students",
  "exam-reports": "exams",
  "leave-report": "leaves",
};

/** Modules that exist on the live Render admin API. */
export const SCHOOL_MODULES: Record<string, SchoolModule> = {
  students: {
    title: "Students",
    endpoint: "/students",
    columns: [
      { key: "admission_no", label: "Admission no" },
      { key: "roll_number", label: "Roll" },
      { key: "class_section_id", label: "Class section" },
      { key: "session_year_id", label: "Session" },
    ],
    fields: [
      { key: "first_name", label: "First name", required: true },
      { key: "last_name", label: "Last name", required: true },
      { key: "email", label: "Email", required: true },
      { key: "admission_no", label: "Admission number", required: true },
      { key: "admission_date", label: "Admission date", type: "date", required: true },
      { key: "class_section_id", label: "Class section ID", type: "number", required: true },
      { key: "session_year_id", label: "Session year ID", type: "number", required: true },
      { key: "guardian_id", label: "Guardian user ID", type: "number", required: true },
      { key: "roll_number", label: "Roll number", type: "number" },
    ],
  },
  classes: {
    title: "Classes",
    endpoint: "/classes",
    columns: [
      { key: "name", label: "Class" },
      { key: "medium_id", label: "Medium" },
    ],
    fields: [
      { key: "name", label: "Class name", required: true },
      { key: "medium_id", label: "Medium ID", type: "number", required: true },
    ],
  },
  subjects: {
    title: "Subjects",
    endpoint: "/subjects",
    columns: [
      { key: "name", label: "Subject" },
      { key: "code", label: "Code" },
      { key: "type", label: "Type" },
    ],
    fields: [
      { key: "name", label: "Subject name", required: true },
      { key: "code", label: "Code" },
      { key: "type", label: "Type" },
      { key: "medium_id", label: "Medium ID", type: "number", required: true },
    ],
  },
  attendance: {
    title: "Attendance",
    endpoint: "/attendances",
    columns: [
      { key: "date", label: "Date" },
      { key: "student_id", label: "Student" },
      { key: "type", label: "Type" },
      { key: "remark", label: "Remark" },
    ],
    fields: [
      { key: "student_id", label: "Student ID", type: "number", required: true },
      { key: "class_section_id", label: "Class section ID", type: "number", required: true },
      { key: "session_year_id", label: "Session year ID", type: "number", required: true },
      { key: "date", label: "Date", type: "date", required: true },
      { key: "type", label: "Type (1 present, 0 absent, 2 late)", type: "number", required: true },
      { key: "remark", label: "Remark" },
    ],
  },
  exams: {
    title: "Exams",
    endpoint: "/exams",
    columns: [
      { key: "name", label: "Exam" },
      { key: "class_id", label: "Class" },
      { key: "publish", label: "Published" },
    ],
    fields: [
      { key: "name", label: "Exam name", required: true },
      { key: "class_id", label: "Class ID", type: "number", required: true },
      { key: "session_year_id", label: "Session year ID", type: "number", required: true },
      { key: "description", label: "Description", type: "textarea" },
      { key: "publish", label: "Publish (1 or 0)", type: "number" },
    ],
  },
  fees: {
    title: "Fees",
    endpoint: "/fees",
    columns: [
      { key: "name", label: "Fee" },
      { key: "due_date", label: "Due date" },
      { key: "due_charges", label: "Due charges" },
    ],
    fields: [
      { key: "name", label: "Fee name", required: true },
      { key: "due_date", label: "Due date", type: "date", required: true },
      { key: "session_year_id", label: "Session year ID", type: "number", required: true },
      { key: "due_charges", label: "Due charges", type: "number" },
    ],
  },
  expenses: {
    title: "Expenses",
    endpoint: "/expenses",
    columns: [
      { key: "title", label: "Expense" },
      { key: "amount", label: "Amount" },
      { key: "date", label: "Date" },
    ],
    fields: [
      { key: "title", label: "Title", required: true },
      { key: "amount", label: "Amount", type: "number", required: true },
      { key: "date", label: "Date", type: "date", required: true },
      { key: "session_year_id", label: "Session year ID", type: "number", required: true },
    ],
  },
  notices: {
    title: "Notices",
    endpoint: "/announcements",
    columns: [
      { key: "title", label: "Title" },
      { key: "description", label: "Description" },
    ],
    fields: [
      { key: "title", label: "Title", required: true },
      { key: "session_year_id", label: "Session year ID", type: "number", required: true },
      { key: "description", label: "Description", type: "textarea" },
    ],
  },
  leaves: {
    title: "Leaves",
    endpoint: "/leaves",
    columns: [
      { key: "reason", label: "Reason" },
      { key: "from_date", label: "From" },
      { key: "to_date", label: "To" },
      { key: "status", label: "Status" },
    ],
    fields: [
      { key: "user_id", label: "User ID", type: "number", required: true },
      { key: "reason", label: "Reason", required: true },
      { key: "from_date", label: "From", type: "date", required: true },
      { key: "to_date", label: "To", type: "date", required: true },
      { key: "session_year_id", label: "Session year ID", type: "number", required: true },
    ],
  },
};
