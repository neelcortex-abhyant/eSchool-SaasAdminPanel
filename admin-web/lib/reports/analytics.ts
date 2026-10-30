/**
 * School reports and analytics: one loader per category, each built on the services the rest
 * of the panel already uses (so the same live/sample switches apply). Server totals come from
 * the backend's report routes (/reports/*, /fees/collection-report, /fees/outstanding,
 * /staff-attendance/reports, /payroll/summary); breakdowns the server doesn't group (by class,
 * by subject, by month) are worked out here from its lists and say so in the notes.
 * Every request goes through the signed-in admin's token, so only that school's data is read.
 */
import { errorMessage, listAll } from "@/lib/academics";
import { getOne, staffDirectory } from "@/lib/extras/api";
import { loadLeaves, loadLeaveTypes } from "@/lib/operations/leave";
import { money, payrollService } from "@/lib/operations/payroll";
import { trackingService } from "@/lib/operations/tracking";
import { feeService } from "@/lib/ops/fees";
import { transportService } from "@/lib/ops/transport";
import { peopleService } from "@/lib/people";
import { attendanceService, tally } from "@/lib/teaching/attendance";
import { num, settleLimited, str, type Raw } from "@/lib/teaching/client";
import { allOfflineExams, offlineService } from "@/lib/teaching/offline";
import type { OfflineResult } from "@/lib/teaching/offlineTypes";

export type ReportCategory = "students" | "academics" | "finance" | "staff" | "transport";

export const REPORT_CATEGORIES: { key: ReportCategory; label: string; filters: ("dates" | "placement")[] }[] = [
  { key: "students", label: "Students", filters: ["dates", "placement"] },
  { key: "academics", label: "Academics", filters: ["dates", "placement"] },
  { key: "finance", label: "Finance", filters: ["dates", "placement"] },
  { key: "staff", label: "Staff", filters: ["dates"] },
  { key: "transport", label: "Transport", filters: ["dates"] },
];

export type ReportFilter = { sessionId: number | ""; classId: number | ""; sectionId: number | ""; from: string; to: string };

export type Card = { label: string; value: string; note?: string; tone?: "success" | "warning" | "danger" };
export type ChartFormat = "count" | "money" | "percent";
export type Chart = { title: string; kind: "bar" | "line"; format: ChartFormat; points: { label: string; value: number }[] };
export type Cell = string | number;
export type ReportTable = { title: string; columns: string[]; rows: Cell[][]; empty: string };
export type Report = { cards: Card[]; charts: Chart[]; tables: ReportTable[]; notes: string[]; warnings: string[] };

export function formatValue(value: number, format: ChartFormat): string {
  if (format === "money") return money(value);
  if (format === "percent") return `${value}%`;
  return value.toLocaleString("en-IN");
}

const pct = (part: number, whole: number) => (whole ? Math.round((part / whole) * 1000) / 10 : 0);
const avg = (values: number[]) => (values.length ? Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 10) / 10 : 0);
const inRange = (date: string | null | undefined, filter: ReportFilter) => !!date && date.slice(0, 10) >= filter.from && date.slice(0, 10) <= filter.to;

/** "2026-04" → "Apr 2026" */
export function monthName(month: string): string {
  const [year, mon] = month.split("-").map(Number);
  if (!year || !mon) return month;
  return new Date(year, mon - 1, 1).toLocaleDateString("en-IN", { month: "short", year: "numeric" });
}

/** Every month from `from` to `to`, so a trend shows months with nothing in them too. */
export function monthsBetween(from: string, to: string): string[] {
  const months: string[] = [];
  let [year, mon] = from.slice(0, 7).split("-").map(Number);
  const [endYear, endMon] = to.slice(0, 7).split("-").map(Number);
  while ((year < endYear || (year === endYear && mon <= endMon)) && months.length < 36) {
    months.push(`${year}-${String(mon).padStart(2, "0")}`);
    mon += 1;
    if (mon > 12) {
      mon = 1;
      year += 1;
    }
  }
  return months;
}

function countBy<T>(rows: T[], key: (row: T) => string): Map<string, number> {
  const counts = new Map<string, number>();
  for (const row of rows) counts.set(key(row), (counts.get(key(row)) ?? 0) + 1);
  return counts;
}

/**
 * Runs the parts of a report side by side. A part that fails becomes a warning so the rest
 * still shows; if every part fails the report fails with the first error.
 */
async function parts<T extends Record<string, () => Promise<unknown>>>(tasks: T): Promise<{ values: { [K in keyof T]: Awaited<ReturnType<T[K]>> | null }; warnings: string[] }> {
  const keys = Object.keys(tasks) as (keyof T)[];
  const settled = await Promise.allSettled(keys.map((key) => tasks[key]()));
  const values = {} as { [K in keyof T]: Awaited<ReturnType<T[K]>> | null };
  const warnings: string[] = [];
  settled.forEach((result, index) => {
    const key = keys[index];
    if (result.status === "fulfilled") values[key] = result.value as Awaited<ReturnType<T[typeof key]>>;
    else {
      values[key] = null;
      warnings.push(`${LABELS[String(key)] ?? String(key)}: ${errorMessage(result.reason, "couldn't be loaded.")}`);
    }
  });
  if (settled.every((result) => result.status === "rejected")) throw (settled[0] as PromiseRejectedResult).reason;
  return { values, warnings };
}

const LABELS: Record<string, string> = {
  students: "Students",
  attendance: "Student attendance",
  enrollment: "Enrollment summary",
  exams: "Exam results",
  collection: "Fee collection",
  outstanding: "Outstanding fees",
  ledger: "Income and expenses",
  staff: "Staff list",
  employment: "Employment summary",
  staffAttendance: "Staff attendance",
  leaves: "Leave",
  payroll: "Payroll summary",
  routes: "Routes",
  vehicles: "Vehicles",
  boarding: "Transport attendance",
};

// ---------- Students ----------

async function studentsReport(filter: ReportFilter): Promise<Report> {
  const { values, warnings } = await parts({
    students: () => listAll((page) => peopleService("students").listStudents({ page, pageSize: 50, sessionYearId: filter.sessionId, classId: filter.classId, classSectionId: filter.sectionId })),
    attendance: () => attendanceService().records({ sessionYearId: filter.sessionId, classSectionId: filter.sectionId, from: filter.from, to: filter.to }),
    enrollment: () => getOne("/reports/students"),
  });
  const students = values.students ?? [];
  const ids = new Set(students.map((student) => student.id));
  const attendance = (values.attendance ?? []).filter((record) => !values.students || ids.has(record.student_id));
  const active = students.filter((student) => student.status === 1).length;
  const admitted = students.filter((student) => inRange(student.admission_date, filter));
  const marks = tally(attendance);

  const placement = new Map<string, { label: string; className: string; section: string; active: number; inactive: number; present: number; marked: number }>();
  for (const student of students) {
    const key = `${student.class_name}|${student.section_name}`;
    const row = placement.get(key) ?? { label: `${student.class_name} ${student.section_name}`.trim(), className: student.class_name, section: student.section_name, active: 0, inactive: 0, present: 0, marked: 0 };
    if (student.status === 1) row.active += 1;
    else row.inactive += 1;
    placement.set(key, row);
  }
  const studentById = new Map(students.map((student) => [student.id, student]));
  for (const record of attendance) {
    const student = studentById.get(record.student_id);
    const row = student ? placement.get(`${student.class_name}|${student.section_name}`) : undefined;
    if (!row) continue;
    row.marked += 1;
    if (record.status === "present" || record.status === "late") row.present += 1;
  }
  const sections = [...placement.values()].sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }));
  const byClass = new Map<string, number>();
  for (const row of sections) byClass.set(row.className, (byClass.get(row.className) ?? 0) + row.active + row.inactive);
  const admissionsByMonth = countBy(admitted, (student) => student.admission_date.slice(0, 7));
  const enrollment = values.enrollment ? Object.entries((values.enrollment.by_enrollment_status as Record<string, unknown>) ?? {}) : [];

  return {
    cards: [
      { label: "Students", value: formatValue(students.length, "count") },
      { label: "Active", value: formatValue(active, "count"), tone: "success" },
      { label: "Inactive", value: formatValue(students.length - active, "count"), tone: students.length - active ? "warning" : undefined },
      { label: "Admitted in period", value: formatValue(admitted.length, "count") },
      { label: "Attendance", value: marks.marked ? `${marks.percent}%` : "—", note: `${formatValue(marks.marked, "count")} marks` },
    ],
    charts: [
      { title: "Students by class", kind: "bar", format: "count", points: [...byClass].map(([label, value]) => ({ label, value })) },
      { title: "Admissions by month", kind: "line", format: "count", points: monthsBetween(filter.from, filter.to).map((month) => ({ label: monthName(month), value: admissionsByMonth.get(month) ?? 0 })) },
    ],
    tables: [
      {
        title: "Students by class and section",
        columns: ["Class", "Section", "Active", "Inactive", "Total", "Attendance"],
        rows: sections.map((row) => [row.className, row.section, row.active, row.inactive, row.active + row.inactive, row.marked ? `${pct(row.present, row.marked)}%` : "—"]),
        empty: "No students match these filters.",
      },
      {
        title: "Attendance summary",
        columns: ["Status", "Marks", "Share"],
        rows: marks.marked ? (["present", "late", "absent", "leave"] as const).map((status) => [status[0].toUpperCase() + status.slice(1), marks[status], `${pct(marks[status], marks.marked)}%`]) : [],
        empty: "No attendance was marked in this period.",
      },
      {
        title: "Enrollment status (whole school, from the server)",
        columns: ["Status", "Students"],
        rows: enrollment.map(([status, count]) => [status, num(count)]),
        empty: "The server returned no enrollment summary.",
      },
    ],
    notes: ["Class, section and month breakdowns are counted here from the server's student and attendance lists. Attendance counts present and late as attended."],
    warnings,
  };
}

// ---------- Academics ----------

const MAX_EXAMS = 20;

async function academicsReport(filter: ReportFilter): Promise<Report> {
  const exams = (await allOfflineExams({ sessionYearId: filter.sessionId, classSectionId: filter.sectionId }))
    .filter((exam) => !filter.classId || exam.class_id === filter.classId)
    .filter((exam) => !exam.exam_date || inRange(exam.exam_date, filter))
    .sort((a, b) => (b.exam_date ?? "").localeCompare(a.exam_date ?? ""));
  const shown = exams.slice(0, MAX_EXAMS);
  const settled = await settleLimited(shown.map((exam) => () => offlineService().results(exam.id)), 4);
  const warnings: string[] = [];
  const results = new Map<number, OfflineResult[]>();
  settled.forEach((result, index) => {
    if (result.ok) results.set(shown[index].id, result.value);
    else warnings.push(`${shown[index].name}: ${errorMessage(result.error, "results couldn't be loaded.")}`);
  });
  const all = [...results.values()].flat();
  const passed = all.filter((row) => row.passed).length;

  const byClass = new Map<string, number[]>();
  for (const exam of shown) {
    const key = `${exam.class_name} ${exam.section_name}`.trim();
    byClass.set(key, [...(byClass.get(key) ?? []), ...(results.get(exam.id) ?? []).map((row) => row.percentage)]);
  }
  const bySubject = new Map<string, { obtained: number[]; percent: number[]; passed: number; papers: number }>();
  for (const row of all) {
    for (const subject of row.subjects) {
      if (!subject.included || subject.marks_obtained === null) continue;
      const name = subject.subject_name ?? `Subject #${subject.subject_id}`;
      const entry = bySubject.get(name) ?? { obtained: [], percent: [], passed: 0, papers: 0 };
      entry.obtained.push(subject.marks_obtained);
      entry.percent.push(subject.max_marks ? (subject.marks_obtained / subject.max_marks) * 100 : 0);
      entry.papers += 1;
      if (subject.passed) entry.passed += 1;
      bySubject.set(name, entry);
    }
  }
  const classRows = [...byClass].filter(([, values]) => values.length).sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }));
  const subjectRows = [...bySubject].sort(([a], [b]) => a.localeCompare(b));

  return {
    cards: [
      { label: "Exams", value: formatValue(exams.length, "count") },
      { label: "Results processed", value: formatValue(all.length, "count") },
      { label: "Passed", value: formatValue(passed, "count"), tone: "success" },
      { label: "Failed", value: formatValue(all.length - passed, "count"), tone: all.length - passed ? "danger" : undefined },
      { label: "Pass rate", value: all.length ? `${pct(passed, all.length)}%` : "—" },
      { label: "Average score", value: all.length ? `${avg(all.map((row) => row.percentage))}%` : "—" },
    ],
    charts: [
      { title: "Average score by class", kind: "bar", format: "percent", points: classRows.map(([label, values]) => ({ label, value: avg(values) })) },
      { title: "Average score by subject", kind: "bar", format: "percent", points: subjectRows.map(([label, entry]) => ({ label, value: avg(entry.percent) })) },
    ],
    tables: [
      {
        title: "Exam results",
        columns: ["Exam", "Class", "Date", "Results", "Passed", "Failed", "Pass rate", "Average"],
        rows: shown.map((exam) => {
          const rows = results.get(exam.id) ?? [];
          const ok = rows.filter((row) => row.passed).length;
          return [exam.name, `${exam.class_name} ${exam.section_name}`.trim(), exam.exam_date ?? "—", rows.length, ok, rows.length - ok, rows.length ? `${pct(ok, rows.length)}%` : "—", rows.length ? `${avg(rows.map((row) => row.percentage))}%` : "—"];
        }),
        empty: "No exams in this period for these filters.",
      },
      {
        title: "Class-wise performance",
        columns: ["Class", "Students", "Average", "Highest", "Lowest"],
        rows: classRows.map(([label, values]) => [label, values.length, `${avg(values)}%`, `${Math.max(...values)}%`, `${Math.min(...values)}%`]),
        empty: "No processed results yet.",
      },
      {
        title: "Subject-wise marks",
        columns: ["Subject", "Papers", "Average marks", "Average %", "Pass rate"],
        rows: subjectRows.map(([name, entry]) => [name, entry.papers, avg(entry.obtained), `${avg(entry.percent)}%`, `${pct(entry.passed, entry.papers)}%`]),
        empty: "No subject marks in the processed results.",
      },
    ],
    notes: [
      "Pass/fail and percentages come from the server's processed results; class and subject averages are worked out here. Exams without processed results show no scores.",
      ...(exams.length > MAX_EXAMS ? [`Showing the latest ${MAX_EXAMS} of ${exams.length} exams; narrow the dates or class to see others.`] : []),
    ],
    warnings,
  };
}

// ---------- Finance ----------

async function financeReport(filter: ReportFilter): Promise<Report> {
  const { values, warnings } = await parts({
    collection: () => feeService().collectionReport(filter.from, filter.to, filter.classId),
    outstanding: () => feeService().outstanding({ sessionYearId: filter.sessionId, classId: filter.classId, classSectionId: filter.sectionId }),
    ledger: () => getOne("/reports/financial-summary"),
  });
  const collection = values.collection;
  const items = collection?.items ?? [];
  const outstanding = values.outstanding ?? [];
  const owed = outstanding.reduce((sum, row) => sum + row.balance, 0);
  const overdue = outstanding.reduce((sum, row) => sum + row.overdue, 0);
  const byMonth = new Map<string, number>();
  for (const item of items) byMonth.set(item.paid_on.slice(0, 7), (byMonth.get(item.paid_on.slice(0, 7)) ?? 0) + item.amount);
  const methods = Object.entries(collection?.by_method ?? {}).sort(([, a], [, b]) => b - a);
  const methodCounts = countBy(items, (item) => item.method);
  const ledger = values.ledger;
  const label = (method: string) => (method.toLowerCase() === "upi" ? "UPI" : method.replace(/_/g, " ").replace(/^\w/, (letter) => letter.toUpperCase()));

  return {
    cards: [
      { label: "Collected in period", value: collection ? money(collection.total_collected) : "—", note: collection ? `${formatValue(collection.payment_count, "count")} payments` : undefined, tone: "success" },
      { label: "Outstanding", value: values.outstanding ? money(owed) : "—", note: values.outstanding ? `${formatValue(outstanding.filter((row) => row.balance > 0).length, "count")} students` : undefined, tone: owed ? "warning" : undefined },
      { label: "Overdue", value: values.outstanding ? money(overdue) : "—", tone: overdue ? "danger" : undefined },
      ...(ledger
        ? [
            { label: "Income (all time)", value: money(num(ledger.income_total)) },
            { label: "Expenses (all time)", value: money(num(ledger.expense_total)) },
            { label: "Net (all time)", value: money(num(ledger.net)), tone: num(ledger.net) < 0 ? ("danger" as const) : undefined },
          ]
        : []),
    ],
    charts: [
      { title: "Fee collection by month", kind: "line", format: "money", points: monthsBetween(filter.from, filter.to).map((month) => ({ label: monthName(month), value: Math.round((byMonth.get(month) ?? 0) * 100) / 100 })) },
      { title: "Collection by payment method", kind: "bar", format: "money", points: methods.map(([method, amount]) => ({ label: label(method), value: amount })) },
    ],
    tables: [
      {
        title: "Payment methods",
        columns: ["Method", "Payments", "Amount", "Share"],
        rows: methods.map(([method, amount]) => [label(method), methodCounts.get(method) ?? 0, money(amount), `${pct(amount, collection?.total_collected ?? 0)}%`]),
        empty: "No payments in this period.",
      },
      {
        title: "Monthly collection",
        columns: ["Month", "Payments", "Amount"],
        rows: monthsBetween(filter.from, filter.to).map((month) => [monthName(month), items.filter((item) => item.paid_on.startsWith(month)).length, money(byMonth.get(month) ?? 0)]),
        empty: "No payments in this period.",
      },
      {
        title: "Largest outstanding balances",
        columns: ["Student", "Admission no.", "Class", "Payable", "Paid", "Balance", "Overdue"],
        rows: outstanding
          .filter((row) => row.balance > 0)
          .sort((a, b) => b.balance - a.balance)
          .slice(0, 50)
          .map((row) => [row.student_name, row.admission_no, `${row.class_name} ${row.section_name}`.trim(), money(row.total - row.concession), money(row.paid), money(row.balance), money(row.overdue)]),
        empty: "Nobody owes fees for these filters.",
      },
    ],
    notes: [
      "Collection totals and payment methods come from the server's collection report for the dates chosen; the section filter applies to outstanding fees only. Income, expenses and net are the server's all-time figures.",
      "The outstanding table lists the 50 largest balances; the CSV has the same rows.",
    ],
    warnings,
  };
}

// ---------- Staff ----------

async function staffReport(filter: ReportFilter): Promise<Report> {
  const year = Number(filter.to.slice(0, 4));
  const { values, warnings } = await parts({
    staff: () => staffDirectory(),
    employment: () => getOne("/reports/staff"),
    staffAttendance: () => getOne("/staff-attendance/reports", { from_date: filter.from, to_date: filter.to }),
    leaves: async () => loadLeaves(await loadLeaveTypes().catch(() => [])),
    payroll: () => payrollService().summary(year),
  });
  const staff = values.staff ?? [];
  const teachers = staff.filter((person) => person.kind === "teacher").length;
  const records = Array.isArray(values.staffAttendance?.items) ? (values.staffAttendance.items as Raw[]) : [];
  const statuses = countBy(records, (record) => {
    const status = str(record.status);
    return status === "half_day" ? "present" : status;
  });
  const attended = (statuses.get("present") ?? 0) + (statuses.get("late") ?? 0);
  const leaves = (values.leaves ?? []).filter((leave) => leave.kind !== "student" && leave.from_date <= filter.to && leave.to_date >= filter.from);
  const leaveTypes = new Map<string, { requests: number; days: number; approved: number; pending: number; rejected: number }>();
  for (const leave of leaves) {
    const key = leave.leave_type ?? "Other";
    const row = leaveTypes.get(key) ?? { requests: 0, days: 0, approved: 0, pending: 0, rejected: 0 };
    row.requests += 1;
    row.days += leave.days;
    if (leave.status === 1) row.approved += 1;
    else if (leave.status === 2) row.rejected += 1;
    else row.pending += 1;
    leaveTypes.set(key, row);
  }
  const departments = countBy(staff, (person) => person.department || (person.kind === "teacher" ? "Teaching" : "Unassigned"));
  const payroll = (values.payroll ?? []).filter((row) => row.processed || row.total_net);
  const employment = values.employment ? Object.entries((values.employment.by_employment_status as Record<string, unknown>) ?? {}) : [];

  return {
    cards: [
      { label: "Staff", value: formatValue(staff.length, "count"), note: `${formatValue(teachers, "count")} teachers` },
      { label: "Attendance", value: records.length ? `${pct(attended, records.length)}%` : "—", note: `${formatValue(records.length, "count")} marks` },
      { label: "Leave requests", value: formatValue(leaves.length, "count"), note: `${formatValue(leaves.reduce((sum, leave) => sum + (leave.status === 1 ? leave.days : 0), 0), "count")} approved days` },
      { label: "Pending leave", value: formatValue(leaves.filter((leave) => leave.status === 0).length, "count"), tone: leaves.some((leave) => leave.status === 0) ? "warning" : undefined },
      { label: `Payroll ${year}`, value: values.payroll ? money(payroll.reduce((sum, row) => sum + row.total_net, 0)) : "—", note: "Net paid" },
    ],
    charts: [
      { title: "Staff by department", kind: "bar", format: "count", points: [...departments].sort(([, a], [, b]) => b - a).map(([label, value]) => ({ label, value })) },
      { title: `Net payroll by month, ${year}`, kind: "line", format: "money", points: (values.payroll ?? []).map((row) => ({ label: monthName(row.month), value: row.total_net })) },
    ],
    tables: [
      {
        title: "Staff attendance summary",
        columns: ["Status", "Marks", "Share"],
        rows: [...statuses].sort(([, a], [, b]) => b - a).map(([status, count]) => [status.replace(/_/g, " ").replace(/^\w/, (letter) => letter.toUpperCase()), count, `${pct(count, records.length)}%`]),
        empty: "No staff attendance was marked in this period.",
      },
      {
        title: "Leave by type",
        columns: ["Leave type", "Requests", "Days", "Approved", "Pending", "Rejected"],
        rows: [...leaveTypes].map(([type, row]) => [type, row.requests, row.days, row.approved, row.pending, row.rejected]),
        empty: "No staff leave in this period.",
      },
      {
        title: `Payroll summary, ${year}`,
        columns: ["Month", "Processed", "Pending", "Failed", "Net paid"],
        rows: payroll.map((row) => [monthName(row.month), row.processed, row.pending, row.failed, money(row.total_net)]),
        empty: `No payroll was processed in ${year}.`,
      },
      {
        title: "Employment status (from the server)",
        columns: ["Status", "Staff"],
        rows: employment.map(([status, count]) => [status, num(count)]),
        empty: "The server returned no employment summary.",
      },
    ],
    notes: ["Class and section filters don't apply to staff. Payroll is shown for the year of the end date. Leave counts staff and teacher requests that overlap the dates chosen."],
    warnings,
  };
}

// ---------- Transport ----------

async function transportReport(filter: ReportFilter): Promise<Report> {
  const { values, warnings } = await parts({
    routes: () => transportService().routes(),
    vehicles: () => transportService().vehicles(),
    boarding: () => trackingService().routeReport(filter.from, filter.to),
  });
  const routes = values.routes ?? [];
  const vehicles = values.vehicles ?? [];
  const boarding = values.boarding ?? [];
  const riders = routes.reduce((sum, route) => sum + route.assigned_students, 0);
  const trips = boarding.reduce((sum, row) => sum + row.trips, 0);
  const expected = boarding.reduce((sum, row) => sum + row.expected, 0);
  const boarded = boarding.reduce((sum, row) => sum + row.boarded, 0);

  return {
    cards: [
      { label: "Routes", value: formatValue(routes.length, "count"), note: `${formatValue(routes.filter((route) => route.status === 1).length, "count")} active` },
      { label: "Vehicles", value: formatValue(vehicles.length, "count"), note: `${formatValue(vehicles.reduce((sum, vehicle) => sum + vehicle.capacity, 0), "count")} seats` },
      { label: "Students on transport", value: formatValue(riders, "count") },
      { label: "Trips in period", value: formatValue(trips, "count") },
      { label: "Boarding rate", value: expected ? `${pct(boarded, expected)}%` : "—" },
    ],
    charts: [
      { title: "Students by route", kind: "bar", format: "count", points: routes.map((route) => ({ label: route.name, value: route.assigned_students })) },
      { title: "Boarding rate by route", kind: "bar", format: "percent", points: boarding.filter((row) => row.expected).map((row) => ({ label: row.route_name, value: pct(row.boarded, row.expected) })) },
    ],
    tables: [
      {
        title: "Routes",
        columns: ["Route", "Vehicle", "Stops", "Capacity", "Students", "Seats used", "Status"],
        rows: routes.map((route) => [route.name, route.vehicle_label ?? "—", route.stops.length, route.capacity ?? "—", route.assigned_students, route.capacity ? `${pct(route.assigned_students, route.capacity)}%` : "—", route.status === 1 ? "Active" : "Inactive"]),
        empty: "No transport routes yet.",
      },
      {
        title: "Transport attendance by route",
        columns: ["Route", "Trips", "Expected", "Boarded", "Absent", "Boarding rate"],
        rows: boarding.map((row) => [row.route_name, row.trips, row.expected, row.boarded, row.absent, row.expected ? `${pct(row.boarded, row.expected)}%` : "—"]),
        empty: "No trips ran in this period.",
      },
      {
        title: "Vehicles",
        columns: ["Registration", "Type", "Capacity", "Driver", "Helper", "Students", "Status"],
        rows: vehicles.map((vehicle) => [vehicle.registration_no, vehicle.vehicle_type, vehicle.capacity, vehicle.driver_name ?? "—", vehicle.helper_name ?? "—", vehicle.assigned_students, vehicle.status === 1 ? "Active" : "Inactive"]),
        empty: "No vehicles yet.",
      },
    ],
    notes: ["Class and section filters don't apply to transport. Route student counts are current assignments; trips and boarding cover the dates chosen."],
    warnings,
  };
}

const LOADERS: Record<ReportCategory, (filter: ReportFilter) => Promise<Report>> = {
  students: studentsReport,
  academics: academicsReport,
  finance: financeReport,
  staff: staffReport,
  transport: transportReport,
};

export function loadReport(category: ReportCategory, filter: ReportFilter): Promise<Report> {
  return LOADERS[category](filter);
}

/** One CSV with every table of the report, each under its title. */
export function reportCsv(report: Report, heading: string): string {
  const cell = (value: unknown) => {
    const text = value === null || value === undefined ? "" : String(value);
    const safe = /^[=+\-@]/.test(text) ? `'${text}` : text;
    return /[",\n\r]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
  };
  const line = (cells: unknown[]) => cells.map(cell).join(",");
  const blocks = [[line([heading]), ...report.cards.map((card) => line([card.label, card.value, card.note ?? ""]))].join("\r\n")];
  for (const table of report.tables) blocks.push([line([table.title]), line(table.columns), ...table.rows.map(line)].join("\r\n"));
  return blocks.join("\r\n\r\n");
}
