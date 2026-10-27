/**
 * The school-admin menu pages built on the routes added in backend 0039, by menu slug
 * (/school/{slug}). Fields and columns follow the server: a field the server's PATCH ignores is
 * `createOnly`, and edit/delete appear only where the server has PATCH/DELETE.
 */
import type { ExtraConfig, FieldDef, ResourceConfig } from "@/lib/extras/types";

const money = (value: unknown) => (value === null || value === undefined || value === "" ? "—" : `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`);

const STATUS_INQUIRY = [
  { value: "open", label: "Open" },
  { value: "contacted", label: "Contacted" },
  { value: "admitted", label: "Admitted" },
  { value: "closed", label: "Closed" },
];

const TASK_STATUS = [
  { value: "pending", label: "Pending" },
  { value: "in_progress", label: "In progress" },
  { value: "done", label: "Done" },
];

const named = (path: string): { path: string; label: string } => ({ path, label: "name" });

const nameAndDescription = (noun: string, path: string, title: string, description: string, canEdit = true): ResourceConfig => ({
  kind: "resource",
  title,
  description,
  path,
  noun,
  fields: [
    { key: "name", label: "Name", type: "text", required: true, maxLength: 255 },
    { key: "description", label: "Description", type: "textarea" },
  ],
  columns: [
    { key: "name", label: "Name" },
    { key: "description", label: "Description" },
  ],
  canEdit,
  canDelete: true,
});

const sessionField: FieldDef = { key: "session_year_id", label: "Academic session", type: "ref", ref: "session", required: true, createOnly: true, defaultCurrent: true };

const LEAVE_STATUS = [
  { value: "0", label: "Pending" },
  { value: "1", label: "Approved" },
  { value: "2", label: "Rejected" },
];

const leaveColumns = [
  { key: "user_id", label: "Person", ref: "staff-user" as const, format: undefined },
  { key: "name", label: "Reason" },
  { key: "from_date", label: "From" },
  { key: "to_date", label: "To" },
  { key: "status", label: "Status", format: (value: unknown) => LEAVE_STATUS.find((item) => item.value === String(value))?.label ?? "—" },
];

export const EXTRA_PAGES: Record<string, ExtraConfig> = {
  // ---------- Academics ----------
  semester: {
    kind: "resource",
    title: "Semesters",
    description: "Terms within an academic session.",
    path: "/semesters",
    noun: "semester",
    fields: [
      { key: "name", label: "Name", type: "text", required: true, maxLength: 255 },
      sessionField,
      { key: "start_date", label: "Starts", type: "date" },
      { key: "end_date", label: "Ends", type: "date" },
    ],
    columns: [
      { key: "name", label: "Name" },
      { key: "session_year_id", label: "Session", ref: "session" },
      { key: "start_date", label: "Starts" },
      { key: "end_date", label: "Ends" },
    ],
    canEdit: true,
    canDelete: true,
    sort: { key: "start_date" },
  },
  stream: nameAndDescription("stream", "/streams", "Streams", "Streams such as Science, Commerce and Arts."),
  shift: {
    kind: "resource",
    title: "Shifts",
    description: "School shifts and their timings.",
    path: "/shifts",
    noun: "shift",
    fields: [
      { key: "name", label: "Name", type: "text", required: true, maxLength: 255 },
      { key: "start_time", label: "Starts", type: "time" },
      { key: "end_time", label: "Ends", type: "time" },
    ],
    columns: [
      { key: "name", label: "Name" },
      { key: "start_time", label: "Starts" },
      { key: "end_time", label: "Ends" },
    ],
    canEdit: true,
    canDelete: true,
    sort: { key: "start_time" },
  },
  syllabus: {
    kind: "resource",
    title: "Syllabus",
    description: "What each class covers in a subject.",
    path: "/syllabi",
    noun: "syllabus",
    fields: [
      { key: "title", label: "Title", type: "text", required: true, maxLength: 255 },
      { ...sessionField, required: false },
      { key: "class_id", label: "Class", type: "ref", ref: "class", createOnly: true },
      { key: "subject_id", label: "Subject", type: "ref", ref: "subject", createOnly: true },
      { key: "content", label: "Content", type: "textarea" },
    ],
    columns: [
      { key: "title", label: "Title" },
      { key: "class_id", label: "Class", ref: "class" },
      { key: "subject_id", label: "Subject", ref: "subject" },
      { key: "session_year_id", label: "Session", ref: "session" },
    ],
    canEdit: true,
    canDelete: true,
  },

  // ---------- Students ----------
  "admission-inquiries": {
    kind: "resource",
    title: "Admission inquiries",
    description: "Families who asked about admission, and where each inquiry stands.",
    path: "/admission-inquiries",
    noun: "inquiry",
    fields: [
      { key: "student_name", label: "Student name", type: "text", required: true, maxLength: 255 },
      { key: "parent_name", label: "Parent name", type: "text", maxLength: 255 },
      { key: "mobile", label: "Mobile", type: "tel", maxLength: 64 },
      { key: "email", label: "Email", type: "email", maxLength: 255 },
      { key: "class_interested", label: "Class wanted", type: "text", maxLength: 128 },
      { key: "status", label: "Status", type: "select", options: STATUS_INQUIRY, initial: "open", required: true },
      { key: "message", label: "Message", type: "textarea" },
    ],
    columns: [
      { key: "student_name", label: "Student" },
      { key: "parent_name", label: "Parent" },
      { key: "mobile", label: "Mobile" },
      { key: "class_interested", label: "Class wanted" },
      { key: "status", label: "Status", format: (value) => STATUS_INQUIRY.find((item) => item.value === value)?.label ?? String(value ?? "—") },
      { key: "created_at", label: "Received" },
    ],
    canEdit: true,
    canDelete: true,
    sort: { key: "created_at", desc: true },
  },

  // ---------- Leave (the academics routes: /academics/leaves) ----------
  "staff-leave": {
    kind: "resource",
    title: "Staff leave",
    description: "Leave for teachers and staff, and whether it's approved.",
    path: "/academics/leaves",
    noun: "leave",
    fields: [
      { key: "user_id", label: "Teacher or staff member", type: "ref", ref: "staff-user", required: true, createOnly: true },
      { key: "reason", label: "Reason", type: "text", required: true, maxLength: 255 },
      { key: "from_date", label: "From", type: "date", required: true },
      { key: "to_date", label: "To", type: "date", required: true },
      sessionField,
      { key: "status", label: "Status", type: "select", options: LEAVE_STATUS, initial: "0", required: true },
    ],
    columns: leaveColumns.map(({ format, ...column }) => (format ? { ...column, format } : column)),
    canEdit: false,
    canDelete: true,
    sort: { key: "from_date", desc: true },
  },
  "student-leave": {
    kind: "resource",
    title: "Student leave",
    description: "Leave recorded for students and staff.",
    path: "/academics/leaves",
    noun: "leave",
    note: "The server needs the student's sign-in account number (their user ID, not the admission number) and doesn't list it yet, so type it in. Ask the server team to add it to the student list so this can become a search box.",
    fields: [
      { key: "user_id", label: "Student's user ID", type: "number", rawId: true, required: true, createOnly: true, hint: "The student's sign-in account number, not the admission number." },
      { key: "reason", label: "Reason", type: "text", required: true, maxLength: 255 },
      { key: "from_date", label: "From", type: "date", required: true },
      { key: "to_date", label: "To", type: "date", required: true },
      sessionField,
      { key: "status", label: "Status", type: "select", options: LEAVE_STATUS, initial: "0", required: true },
    ],
    columns: leaveColumns.map(({ format, ...column }) => (format ? { ...column, format } : column)),
    canEdit: false,
    canDelete: true,
    sort: { key: "from_date", desc: true },
  },
  "leave-report": {
    kind: "resource",
    title: "Leave report",
    description: "Every leave on record.",
    path: "/academics/leaves",
    noun: "leave",
    fields: [],
    columns: leaveColumns.map(({ format, ...column }) => (format ? { ...column, format } : column)),
    canCreate: false,
    canEdit: false,
    canDelete: false,
    sort: { key: "from_date", desc: true },
  },

  // ---------- Timetable, holidays, online classes ----------
  "online-classes": {
    kind: "resource",
    title: "Online classes",
    description: "Scheduled live classes with their meeting links.",
    path: "/online-classes",
    noun: "online class",
    fields: [
      { key: "title", label: "Title", type: "text", required: true, maxLength: 255 },
      { key: "class_section_id", label: "Class and section", type: "ref", ref: "section", createOnly: true },
      { key: "subject_id", label: "Subject", type: "ref", ref: "subject", createOnly: true },
      { key: "teacher_user_id", label: "Teacher", type: "ref", ref: "teacher", createOnly: true },
      { key: "scheduled_at", label: "Starts at", type: "datetime" },
      { key: "duration_minutes", label: "Duration (minutes)", type: "number" },
      { key: "meeting_url", label: "Meeting link", type: "url", span: true },
    ],
    columns: [
      { key: "title", label: "Title" },
      { key: "class_section_id", label: "Class", ref: "section" },
      { key: "subject_id", label: "Subject", ref: "subject" },
      { key: "teacher_user_id", label: "Teacher", ref: "teacher" },
      { key: "scheduled_at", label: "Starts at" },
      { key: "duration_minutes", label: "Minutes" },
      { key: "meeting_url", label: "Link" },
    ],
    canEdit: true,
    canDelete: true,
    sort: { key: "scheduled_at", desc: true },
  },
  "holiday-list": {
    kind: "resource",
    title: "Holiday list",
    description: "School holidays shown to staff, students and parents.",
    path: "/holidays",
    noun: "holiday",
    fields: [
      { key: "title", label: "Title", type: "text", required: true, maxLength: 255 },
      { key: "holiday_date", label: "Date", type: "date", required: true },
      { key: "end_date", label: "Until (for several days)", type: "date" },
      { key: "description", label: "Description", type: "textarea" },
    ],
    columns: [
      { key: "title", label: "Holiday" },
      { key: "holiday_date", label: "Date" },
      { key: "end_date", label: "Until" },
      { key: "description", label: "Description" },
    ],
    canEdit: true,
    canDelete: true,
    sort: { key: "holiday_date" },
  },

  // ---------- Diaries ----------
  "diary-category": {
    ...nameAndDescription("category", "/diary-categories", "Diary categories", "Categories for student diary notes, such as Behaviour or Achievement.", false),
    fields: [{ key: "name", label: "Name", type: "text", required: true, maxLength: 255 }],
    columns: [{ key: "name", label: "Name" }],
  },
  "student-diary": {
    kind: "resource",
    title: "Student diary",
    description: "Notes about a student, filed by category.",
    path: "/student-diaries",
    noun: "diary note",
    fields: [
      { key: "student_id", label: "Student", type: "ref", ref: "student", required: true },
      { key: "category_id", label: "Category", type: "ref", ref: named("/diary-categories") },
      { key: "title", label: "Title", type: "text", required: true, maxLength: 255 },
      { key: "entry_date", label: "Date", type: "date" },
      { key: "body", label: "Note", type: "textarea" },
    ],
    columns: [
      { key: "entry_date", label: "Date" },
      { key: "student_id", label: "Student", ref: "student" },
      { key: "category_id", label: "Category", ref: named("/diary-categories") },
      { key: "title", label: "Title" },
    ],
    canEdit: false,
    canDelete: true,
    sort: { key: "entry_date", desc: true },
  },

  // ---------- Communication and website ----------
  notification: {
    kind: "resource",
    title: "Notifications",
    description: "Messages sent to the school's users.",
    path: "/notifications",
    noun: "notification",
    note: "The server keeps notifications once sent: they can't be edited or deleted here.",
    fields: [
      { key: "title", label: "Title", type: "text", required: true, maxLength: 255 },
      { key: "body", label: "Message", type: "textarea" },
    ],
    columns: [
      { key: "title", label: "Title" },
      { key: "body", label: "Message" },
      { key: "created_at", label: "Sent" },
    ],
    canEdit: false,
    canDelete: false,
    sort: { key: "created_at", desc: true },
  },
  announcement: {
    kind: "resource",
    title: "Announcements",
    description: "Announcements for an academic session.",
    path: "/announcements",
    noun: "announcement",
    note: "The server keeps announcements once posted: they can't be edited or deleted here.",
    fields: [
      { key: "title", label: "Title", type: "text", required: true, maxLength: 255 },
      sessionField,
      { key: "description", label: "Details", type: "textarea" },
    ],
    columns: [
      { key: "title", label: "Title" },
      { key: "session_year_id", label: "Session", ref: "session" },
      { key: "description", label: "Details" },
      { key: "created_at", label: "Posted" },
    ],
    canEdit: false,
    canDelete: false,
    sort: { key: "created_at", desc: true },
  },
  sliders: {
    kind: "resource",
    title: "Sliders",
    description: "Banner images at the top of the school website.",
    path: "/sliders",
    noun: "slider",
    note: "Paste the address of an image that's already online. After a slider is added, only its order and visibility can be changed.",
    fields: [
      { key: "title", label: "Title", type: "text", required: true, maxLength: 255, createOnly: true },
      { key: "image_url", label: "Image link", type: "url", span: true, createOnly: true },
      { key: "link_url", label: "Opens this link when clicked", type: "url", span: true, createOnly: true },
      { key: "sort_order", label: "Order", type: "number", initial: "0" },
      { key: "status", label: "Shown on the website", type: "checkbox", initial: "1" },
    ],
    columns: [
      { key: "sort_order", label: "Order" },
      { key: "title", label: "Title" },
      { key: "image_url", label: "Image" },
      { key: "status", label: "Shown", format: (value) => (Number(value) === 1 ? "Yes" : "No") },
    ],
    canEdit: true,
    canDelete: true,
    sort: { key: "sort_order" },
  },
  gallery: {
    kind: "resource",
    title: "Gallery",
    description: "Photos for the school website's gallery.",
    path: "/gallery",
    noun: "photo",
    note: "Paste the address of an image that's already online.",
    fields: [
      { key: "title", label: "Title", type: "text", required: true, maxLength: 255 },
      { key: "image_url", label: "Image link", type: "url", span: true },
      { key: "sort_order", label: "Order", type: "number", initial: "0" },
    ],
    columns: [
      { key: "sort_order", label: "Order" },
      { key: "title", label: "Title" },
      { key: "image_url", label: "Image" },
    ],
    canEdit: false,
    canDelete: true,
    sort: { key: "sort_order" },
  },

  // ---------- Staff ----------
  tasks: {
    kind: "resource",
    title: "Tasks",
    description: "Work assigned to staff, with due dates.",
    path: "/staff-tasks",
    noun: "task",
    fields: [
      { key: "title", label: "Task", type: "text", required: true, maxLength: 255 },
      { key: "assigned_to_staff_id", label: "Assigned to", type: "ref", ref: "staff" },
      { key: "due_date", label: "Due", type: "date" },
      { key: "status", label: "Status", type: "select", options: TASK_STATUS, initial: "pending", required: true },
      { key: "description", label: "Details", type: "textarea" },
    ],
    columns: [
      { key: "title", label: "Task" },
      { key: "assigned_to_staff_id", label: "Assigned to", ref: "staff" },
      { key: "due_date", label: "Due" },
      { key: "status", label: "Status", format: (value) => TASK_STATUS.find((item) => item.value === value)?.label ?? String(value ?? "—") },
    ],
    canEdit: true,
    canDelete: true,
    sort: { key: "due_date" },
  },
  "qr-attendance-settings": {
    kind: "settings",
    title: "QR attendance settings",
    description: "Whether staff can mark attendance by scanning the school's QR code.",
    path: "/staff-qr-attendance-settings",
    fields: [
      { key: "enabled", label: "Staff can mark attendance with the QR code", type: "checkbox" },
      { key: "token", label: "QR code token", type: "text", maxLength: 128, hint: "Changing it makes old printed QR codes stop working." },
    ],
  },

  // ---------- Finance ----------
  "manage-expense": {
    kind: "resource",
    title: "Manage expense",
    description: "Money the school spends.",
    path: "/academics/expenses",
    noun: "expense",
    fields: [
      { key: "title", label: "Title", type: "text", required: true, maxLength: 255 },
      { key: "amount", label: "Amount (₹)", type: "number", required: true },
      { key: "date", label: "Date", type: "date", required: true },
      sessionField,
    ],
    columns: [
      { key: "date", label: "Date" },
      { key: "title", label: "Title" },
      { key: "amount", label: "Amount", format: money },
    ],
    canEdit: true,
    canDelete: true,
    sort: { key: "date", desc: true },
  },
  "manage-fees": {
    kind: "resource",
    title: "Fee amounts (server)",
    description: "Session fees with a due date and late charges.",
    path: "/academics/fees",
    noun: "fee",
    fields: [
      { key: "name", label: "Name", type: "text", required: true, maxLength: 255 },
      { key: "due_date", label: "Due date", type: "date", required: true },
      { key: "due_charges", label: "Late charges (₹)", type: "number" },
      sessionField,
    ],
    columns: [
      { key: "name", label: "Fee" },
      { key: "due_date", label: "Due" },
      { key: "due_charges", label: "Late charges", format: money },
    ],
    canEdit: true,
    canDelete: true,
    sort: { key: "due_date" },
  },
  "manage-expense-category": nameAndDescription("category", "/expense-categories", "Expense categories", "Categories for the school's spending."),
  "manage-income-category": {
    ...nameAndDescription("category", "/income-categories", "Income categories", "Categories for income other than student fees.", false),
  },
  "manage-income": {
    kind: "resource",
    title: "Manage income",
    description: "Money the school receives other than student fees.",
    path: "/incomes",
    noun: "income",
    fields: [
      { key: "title", label: "Title", type: "text", required: true, maxLength: 255 },
      { key: "amount", label: "Amount (₹)", type: "number", required: true },
      { key: "income_date", label: "Date", type: "date" },
      { key: "category_id", label: "Category", type: "ref", ref: named("/income-categories"), createOnly: true },
      { ...sessionField, required: false },
    ],
    columns: [
      { key: "income_date", label: "Date" },
      { key: "title", label: "Title" },
      { key: "category_id", label: "Category", ref: named("/income-categories") },
      { key: "amount", label: "Amount", format: money },
    ],
    canEdit: true,
    canDelete: true,
    sort: { key: "income_date", desc: true },
  },
  "income-dashboard": {
    kind: "report",
    title: "Income dashboard",
    description: "Income, spending and what's left, across all records.",
    paths: [{ path: "/incomes/dashboard", title: "Overview" }],
  },
  "payroll-settings": {
    kind: "settings",
    title: "Payroll settings",
    description: "When staff are paid and in which currency.",
    path: "/payroll-settings",
    fields: [
      { key: "pay_day", label: "Pay day (day of the month)", type: "number", hint: "1 to 31" },
      { key: "currency", label: "Currency", type: "text", maxLength: 8, initial: "INR" },
      { key: "notes", label: "Notes", type: "textarea" },
    ],
  },

  // ---------- Certificates and ID cards ----------
  "certificate-template": {
    kind: "resource",
    title: "Certificate templates",
    description: "Wording for certificates such as bonafide, character or leaving certificates.",
    path: "/certificate-templates",
    noun: "template",
    note: "Write the certificate text. Placeholders such as {student_name} are filled in when a certificate is issued.",
    fields: [
      { key: "name", label: "Name", type: "text", required: true, maxLength: 255 },
      { key: "template_type", label: "Type", type: "text", maxLength: 64, initial: "general", hint: "For example bonafide, character or leaving." },
      { key: "body_text", label: "Certificate text", type: "textarea" },
    ],
    columns: [
      { key: "name", label: "Name" },
      { key: "template_type", label: "Type" },
    ],
    canEdit: true,
    canDelete: true,
  },

  // ---------- Subscription ----------
  plans: {
    kind: "resource",
    title: "Plans",
    description: "The subscription plans available to the school.",
    path: "/subscription/plans",
    noun: "plan",
    fields: [],
    columns: [
      { key: "name", label: "Plan" },
      { key: "description", label: "Description" },
      { key: "monthly_price", label: "Monthly", format: money },
      { key: "yearly_price", label: "Yearly", format: money },
      { key: "student_limit", label: "Students" },
      { key: "staff_limit", label: "Staff" },
    ],
    canCreate: false,
    canEdit: false,
    canDelete: false,
    note: "To change plan, go to Subscription.",
  },
  addons: {
    kind: "resource",
    title: "Add-ons",
    description: "Extra features the school can add to its plan.",
    path: "/subscription/addons",
    noun: "add-on",
    fields: [],
    columns: [
      { key: "name", label: "Add-on" },
      { key: "description", label: "Description" },
      { key: "price", label: "Price", format: money },
    ],
    canCreate: false,
    canEdit: false,
    canDelete: false,
  },

  // ---------- Reports ----------
  "student-reports": { kind: "report", title: "Student reports", description: "Students by enrollment status.", paths: [{ path: "/reports/students", title: "Students" }] },
  "teacher-reports": { kind: "report", title: "Teacher reports", description: "Teaching staff on record.", paths: [{ path: "/reports/teachers", title: "Teachers" }] },
  "staff-reports": { kind: "report", title: "Staff reports", description: "Staff by employment status.", paths: [{ path: "/reports/staff", title: "Staff" }] },
  "exam-reports": { kind: "report", title: "Exam reports", description: "Offline exams and processed results.", paths: [{ path: "/reports/exams", title: "Exams" }] },
  "expense-report": { kind: "report", title: "Expense report", description: "All recorded spending.", paths: [{ path: "/reports/expenses", title: "Expenses" }], money: ["total_amount"] },
  "income-report": { kind: "report", title: "Income report", description: "All recorded income other than fees.", paths: [{ path: "/reports/income", title: "Income" }], money: ["total_amount"] },
  "financial-summary-report": {
    kind: "report",
    title: "Financial summary",
    description: "Income, fees collected and spending.",
    paths: [{ path: "/reports/financial-summary", title: "Summary" }],
    money: ["income_total", "expense_total", "fees_collected", "net"],
  },
};
