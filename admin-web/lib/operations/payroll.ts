/**
 * Salary structures, payroll processing and payslips.
 * Live (contract, see backend/docs/OPERATIONS_MODULES_API_CONTRACT.md):
 *   GET/POST /school-admin/salary-structures, PATCH/DELETE /salary-structures/{id}
 *   GET/POST /school-admin/salary-assignments
 *   GET  /school-admin/payroll/preview?month=YYYY-MM   (the server works out every amount)
 *   POST /school-admin/payroll/process {month}         (Idempotency-Key header; 409 if done)
 *   GET  /school-admin/payslips, /payslips/{id}, /payroll/summary?year=
 * Sample: structures, assignments and payslips are kept in this browser. The sample stands in
 * for the server's calculation: it uses the people list and the school's real staff attendance
 * (unpaid absence is deducted pro rata). The page never sends amounts it worked out itself.
 */
import { getOne, staffDirectory, type StaffRef } from "@/lib/extras/api";
import { isOperationsLive } from "@/lib/operations/mode";
import type { Page, PayrollPreview, PayrollPreviewLine, PayrollStatus, Payslip, PayslipQuery, SalaryAssignment, SalaryLine, SalaryStructure, SalaryStructureInput } from "@/lib/operations/types";
import { conflict, invalid, later, missing, nextId } from "@/lib/ops/store";
import { allPages, get, num, optStr, pageOf, request, send, str, type Raw } from "@/lib/teaching/client";

export interface PayrollService {
  structures(): Promise<SalaryStructure[]>;
  saveStructure(input: SalaryStructureInput, id?: number): Promise<SalaryStructure>;
  removeStructure(id: number): Promise<void>;
  assignments(): Promise<SalaryAssignment[]>;
  assign(staffIds: number[], structureId: number, effectiveFrom: string): Promise<void>;
  preview(month: string): Promise<PayrollPreview>;
  process(month: string, idempotencyKey: string): Promise<{ processed: number; failed: number }>;
  payslips(query?: PayslipQuery): Promise<Page<Payslip>>;
  payslip(id: number): Promise<Payslip>;
  summary(year: number): Promise<MonthSummary[]>;
}

export type MonthSummary = { month: string; processed: number; pending: number; failed: number; total_net: number };

export type SalaryComponent = { id: number; name: string; code: string | null; kind: "earning" | "deduction"; calc_type: "fixed" | "percent"; default_value: number };

/** The school's active salary components (server route GET /school-admin/salary-components). */
export async function salaryComponents(): Promise<SalaryComponent[]> {
  const rows = await allPages("/school-admin/salary-components", { active_only: 1 }, "Unable to load salary components.");
  return rows
    .map((row) => ({ id: num(row.id), name: str(row.name), code: optStr(row.code), kind: (str(row.kind) === "deduction" ? "deduction" : "earning") as SalaryComponent["kind"], calc_type: (str(row.calc_type) === "percent" ? "percent" : "fixed") as SalaryComponent["calc_type"], default_value: num(row.default_value) }))
    .filter((row) => row.name);
}

export function money(value: number): string {
  return `₹${value.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

const round = (value: number) => Math.round(value * 100) / 100;

export function structureTotals(input: Pick<SalaryStructureInput, "basic" | "allowances" | "deductions">) {
  const allowances = round(input.allowances.reduce((sum, line) => sum + (line.amount || 0), 0));
  const deductions = round(input.deductions.reduce((sum, line) => sum + (line.amount || 0), 0));
  const gross = round((input.basic || 0) + allowances);
  return { allowances, deductions, gross, net: round(gross - deductions) };
}

export function structureProblems(input: SalaryStructureInput): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!input.name.trim()) errors.name = "Enter a name for the structure.";
  if (!(input.basic > 0)) errors.basic = "Basic salary must be more than 0.";
  const check = (lines: SalaryLine[], key: "allowances" | "deductions") => {
    const names = new Set<string>();
    lines.forEach((line, index) => {
      if (!line.name.trim()) errors[`${key}.${index}`] = "Give this line a name.";
      else if (names.has(line.name.trim().toLowerCase())) errors[`${key}.${index}`] = "This name is used twice.";
      else if (!(line.amount >= 0)) errors[`${key}.${index}`] = "Amounts can't be negative.";
      names.add(line.name.trim().toLowerCase());
    });
  };
  check(input.allowances, "allowances");
  check(input.deductions, "deductions");
  if (!errors.basic && structureTotals(input).net < 0) errors.deductions = "Deductions are more than the gross salary.";
  return errors;
}

/** "2026-10" → "October 2026". */
export function monthLabel(month: string): string {
  const [year, value] = month.split("-").map(Number);
  if (!year || !value) return month;
  return new Date(year, value - 1, 1).toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}

export function isMonth(value: string): boolean {
  return /^\d{4}-(0[1-9]|1[0-2])$/.test(value);
}

// ---------- live ----------

const P = "/school-admin";

function lines(value: unknown): SalaryLine[] {
  return Array.isArray(value) ? (value as Raw[]).map((row) => ({ name: str(row.name), amount: num(row.amount) })) : [];
}

function structureOf(row: Raw): SalaryStructure {
  const base = { basic: num(row.basic), allowances: lines(row.allowances), deductions: lines(row.deductions) };
  const totals = structureTotals(base);
  return { id: num(row.id), name: str(row.name), ...base, gross: num(row.gross ?? totals.gross), net: num(row.net ?? totals.net), assigned: num(row.assigned) };
}

function payslipOf(row: Raw): Payslip {
  return {
    id: num(row.id),
    month: str(row.month),
    staff_id: num(row.staff_id),
    name: str(row.name),
    employee_code: str(row.employee_code),
    department: str(row.department),
    designation: str(row.designation),
    basic: num(row.basic),
    allowances: lines(row.allowances),
    deductions: lines(row.deductions),
    attendance_adjustment: num(row.attendance_adjustment),
    working_days: num(row.working_days),
    paid_days: num(row.paid_days),
    gross: num(row.gross),
    net: num(row.net),
    status: (str(row.status, "processed") as PayrollStatus),
    processed_at: optStr(row.processed_at),
    failure_reason: optStr(row.failure_reason),
  };
}

function previewLineOf(row: Raw): PayrollPreviewLine {
  return {
    staff_id: num(row.staff_id),
    name: str(row.name),
    department: str(row.department),
    structure_name: optStr(row.structure_name),
    basic: num(row.basic),
    allowances: num(row.allowances),
    deductions: num(row.deductions),
    attendance_adjustment: num(row.attendance_adjustment),
    working_days: num(row.working_days),
    paid_days: num(row.paid_days),
    net: num(row.net),
    eligible: row.eligible !== false,
    problem: optStr(row.problem),
  };
}

export const livePayroll: PayrollService = {
  async structures() {
    const data = await get(`${P}/salary-structures`, { page_size: 50 }, "Unable to load salary structures.");
    return (Array.isArray(data.items) ? (data.items as Raw[]) : []).map(structureOf);
  },
  async saveStructure(input, id) {
    const problems = structureProblems(input);
    if (Object.keys(problems).length) invalid(problems);
    const body = { name: input.name.trim(), basic: input.basic, allowances: input.allowances, deductions: input.deductions };
    return structureOf(id ? await send("PATCH", `${P}/salary-structures/${id}`, body, "Unable to save the structure.") : await send("POST", `${P}/salary-structures`, body, "Unable to add the structure."));
  },
  async removeStructure(id) {
    await send("DELETE", `${P}/salary-structures/${id}`, undefined, "Unable to delete the structure.");
  },
  async assignments() {
    const data = await get(`${P}/salary-assignments`, { page_size: 50 }, "Unable to load assignments.");
    return (Array.isArray(data.items) ? (data.items as Raw[]) : []).map((row) => ({ staff_id: num(row.staff_id), structure_id: num(row.structure_id), structure_name: str(row.structure_name), effective_from: str(row.effective_from) }));
  },
  async assign(staffIds, structureId, effectiveFrom) {
    await send("POST", `${P}/salary-assignments`, { staff_ids: staffIds, structure_id: structureId, effective_from: effectiveFrom }, "Unable to assign the structure.");
  },
  async preview(month) {
    const data = await get(`${P}/payroll/preview`, { month }, "Unable to load the payroll.");
    const items = (Array.isArray(data.items) ? (data.items as Raw[]) : []).map(previewLineOf);
    return { month, lines: items, total_net: num(data.total_net ?? items.filter((row) => row.eligible).reduce((sum, row) => sum + row.net, 0)), already_processed: data.already_processed === true };
  },
  async process(month, idempotencyKey) {
    const data = await request<Raw>(`${P}/payroll/process`, { method: "POST", body: JSON.stringify({ month }), headers: { "Idempotency-Key": idempotencyKey } }, "Unable to process the payroll.");
    return { processed: num(data.processed), failed: num(data.failed) };
  },
  async payslips(query = {}) {
    return pageOf(await get(`${P}/payslips`, { page: query.page ?? 1, page_size: Math.min(query.pageSize ?? 20, 50), month: query.month, staff_id: query.staffId, status: query.status, department: query.department }, "Unable to load payslips."), payslipOf);
  },
  async payslip(id) {
    return payslipOf(await get(`${P}/payslips/${id}`, {}, "Unable to load the payslip."));
  },
  async summary(year) {
    const data = await get(`${P}/payroll/summary`, { year }, "Unable to load the payroll summary.");
    return (Array.isArray(data.items) ? (data.items as Raw[]) : []).map((row) => ({ month: str(row.month), processed: num(row.processed), pending: num(row.pending), failed: num(row.failed), total_net: num(row.total_net) }));
  },
};

// ---------- sample ----------

const KEY = "operations-payroll-v1";

type Store = {
  structures: (SalaryStructureInput & { id: number })[];
  assignments: SalaryAssignment[];
  payslips: Payslip[];
  keys: Record<string, { processed: number; failed: number }>;
};

const SEED: Store = {
  structures: [
    { id: 1, name: "Teacher – standard", basic: 30000, allowances: [{ name: "HRA", amount: 8000 }, { name: "Travel", amount: 2000 }], deductions: [{ name: "PF", amount: 3600 }, { name: "Professional tax", amount: 200 }] },
    { id: 2, name: "Office staff", basic: 18000, allowances: [{ name: "HRA", amount: 4000 }], deductions: [{ name: "PF", amount: 2160 }] },
    { id: 3, name: "Driver / helper", basic: 14000, allowances: [{ name: "Overtime (fixed)", amount: 2000 }], deductions: [{ name: "PF", amount: 1680 }] },
  ],
  assignments: [],
  payslips: [],
  keys: {},
};

let memory: Store | null = null;

function store(): Store {
  if (memory) return memory;
  try {
    const saved = window.localStorage.getItem(KEY);
    if (saved) memory = JSON.parse(saved) as Store;
  } catch {
    memory = null;
  }
  memory ??= JSON.parse(JSON.stringify(SEED)) as Store;
  return memory;
}

function save() {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(memory));
  } catch {
    // Storage full or blocked: changes last until the page reloads.
  }
}

export function resetPayrollMock(): void {
  memory = JSON.parse(JSON.stringify(SEED)) as Store;
  save();
}

function structureOut(row: Store["structures"][number]): SalaryStructure {
  const totals = structureTotals(row);
  return { ...row, gross: totals.gross, net: totals.net, assigned: store().assignments.filter((item) => item.structure_id === row.id).length };
}

function monthRange(month: string): { from: string; to: string; days: number } {
  const [year, value] = month.split("-").map(Number);
  const last = new Date(year, value, 0).getDate();
  return { from: `${month}-01`, to: `${month}-${String(last).padStart(2, "0")}`, days: last };
}

/** Monday–Saturday days in a month. */
export function monthWorkingDays(month: string): number {
  const { days } = monthRange(month);
  const [year, value] = month.split("-").map(Number);
  let count = 0;
  for (let day = 1; day <= days; day += 1) if (new Date(year, value - 1, day).getDay() !== 0) count += 1;
  return count;
}

/** The sample server's calculation: structure amounts, less pay for unpaid absent days. */
export function previewLine(person: StaffRef, structure: SalaryStructure | null, absentDays: number, workingDays: number): PayrollPreviewLine {
  if (!structure) {
    return { staff_id: person.staff_id, name: person.name, department: person.department ?? "", structure_name: null, basic: 0, allowances: 0, deductions: 0, attendance_adjustment: 0, working_days: workingDays, paid_days: 0, net: 0, eligible: false, problem: "No salary structure assigned" };
  }
  const totals = structureTotals(structure);
  const unpaid = Math.min(absentDays, workingDays);
  const adjustment = workingDays ? round((totals.gross / workingDays) * unpaid) : 0;
  return {
    staff_id: person.staff_id,
    name: person.name,
    department: person.department ?? "",
    structure_name: structure.name,
    basic: structure.basic,
    allowances: totals.allowances,
    deductions: totals.deductions,
    attendance_adjustment: adjustment,
    working_days: workingDays,
    paid_days: workingDays - unpaid,
    net: round(Math.max(totals.net - adjustment, 0)),
    eligible: true,
    problem: null,
  };
}

async function absences(month: string): Promise<Map<number, number>> {
  const { from, to } = monthRange(month);
  const absent = new Map<number, number>();
  try {
    const data = await getOne("/staff-attendance/reports", { from_date: from, to_date: to });
    for (const row of Array.isArray(data.items) ? (data.items as Raw[]) : []) {
      if (str(row.status) === "absent") absent.set(num(row.staff_id), (absent.get(num(row.staff_id)) ?? 0) + 1);
    }
  } catch {
    // Attendance couldn't be read: the sample pays full days.
  }
  return absent;
}

async function samplePreview(month: string): Promise<PayrollPreview> {
  const db = store();
  const [people, absent] = await Promise.all([staffDirectory(), absences(month)]);
  const working = monthWorkingDays(month);
  const lines = people.map((person) => {
    const assignment = db.assignments.find((row) => row.staff_id === person.staff_id && row.effective_from.slice(0, 7) <= month);
    const structure = assignment ? db.structures.find((row) => row.id === assignment.structure_id) : undefined;
    return previewLine(person, structure ? structureOut(structure) : null, absent.get(person.staff_id) ?? 0, working);
  });
  return { month, lines, total_net: round(lines.filter((row) => row.eligible).reduce((sum, row) => sum + row.net, 0)), already_processed: db.payslips.some((row) => row.month === month && row.status === "processed") };
}

function paginate<T>(rows: T[], page = 1, pageSize = 20): Page<T> {
  const size = Math.min(pageSize, 50);
  const current = Math.max(page, 1);
  return { items: rows.slice((current - 1) * size, current * size), total: rows.length, page: current, page_size: size };
}

export const mockPayroll: PayrollService = {
  async structures() {
    return later(store().structures.map(structureOut).sort((a, b) => a.name.localeCompare(b.name)));
  },
  async saveStructure(input, id) {
    const problems = structureProblems(input);
    if (Object.keys(problems).length) invalid(problems);
    const db = store();
    if (db.structures.some((row) => row.id !== id && row.name.trim().toLowerCase() === input.name.trim().toLowerCase())) conflict("A structure with this name already exists.", "name");
    const row = { id: id ?? nextId(db.structures), name: input.name.trim(), basic: input.basic, allowances: input.allowances.map((line) => ({ name: line.name.trim(), amount: line.amount })), deductions: input.deductions.map((line) => ({ name: line.name.trim(), amount: line.amount })) };
    const index = db.structures.findIndex((item) => item.id === id);
    if (id && index < 0) missing("Salary structure");
    if (index >= 0) db.structures[index] = row;
    else db.structures.push(row);
    save();
    return later(structureOut(row));
  },
  async removeStructure(id) {
    const db = store();
    if (db.assignments.some((row) => row.structure_id === id)) conflict("Employees are on this structure. Move them to another one first.");
    db.structures = db.structures.filter((row) => row.id !== id);
    save();
    await later(null);
  },
  async assignments() {
    return later(store().assignments);
  },
  async assign(staffIds, structureId, effectiveFrom) {
    if (!staffIds.length) invalid({ staff: "Choose at least one employee." });
    if (!/^\d{4}-\d{2}-\d{2}$/.test(effectiveFrom)) invalid({ effective_from: "Choose the date it starts." });
    const db = store();
    const structure = db.structures.find((row) => row.id === structureId) ?? missing("Salary structure");
    db.assignments = [...db.assignments.filter((row) => !staffIds.includes(row.staff_id)), ...staffIds.map((staff_id) => ({ staff_id, structure_id: structure.id, structure_name: structure.name, effective_from: effectiveFrom }))];
    save();
    await later(null);
  },
  async preview(month) {
    if (!isMonth(month)) invalid({ month: "Choose a month." });
    return later(await samplePreview(month));
  },
  async process(month, idempotencyKey) {
    const db = store();
    // A retried request with the same key gets the first answer back.
    if (db.keys[idempotencyKey]) return later(db.keys[idempotencyKey]);
    if (db.payslips.some((row) => row.month === month && row.status === "processed")) conflict(`Payroll for ${monthLabel(month)} has already been processed.`);
    const preview = await samplePreview(month);
    const people = await staffDirectory();
    let id = db.payslips.reduce((max, row) => Math.max(max, row.id), 0);
    const now = new Date().toISOString();
    db.payslips = db.payslips.filter((row) => row.month !== month);
    for (const line of preview.lines.filter((row) => row.eligible)) {
      const person = people.find((row) => row.staff_id === line.staff_id);
      const assignment = db.assignments.find((row) => row.staff_id === line.staff_id);
      const structure = db.structures.find((row) => row.id === assignment?.structure_id);
      const failed = line.net <= 0;
      db.payslips.push({
        id: (id += 1),
        month,
        staff_id: line.staff_id,
        name: line.name,
        employee_code: person?.employee_code ?? "",
        department: line.department,
        designation: person?.designation ?? "",
        basic: line.basic,
        allowances: structure?.allowances ?? [],
        deductions: structure?.deductions ?? [],
        attendance_adjustment: line.attendance_adjustment,
        working_days: line.working_days,
        paid_days: line.paid_days,
        gross: round(line.basic + line.allowances),
        net: line.net,
        status: failed ? "failed" : "processed",
        processed_at: failed ? null : now,
        failure_reason: failed ? "Net pay is zero after deductions and absence." : null,
      });
    }
    const result = { processed: db.payslips.filter((row) => row.month === month && row.status === "processed").length, failed: db.payslips.filter((row) => row.month === month && row.status === "failed").length };
    db.keys[idempotencyKey] = result;
    save();
    return later(result);
  },
  async payslips(query = {}) {
    const rows = store()
      .payslips.filter((row) => !query.month || row.month === query.month)
      .filter((row) => !query.staffId || row.staff_id === query.staffId)
      .filter((row) => !query.status || row.status === query.status)
      .filter((row) => !query.department || row.department === query.department)
      .sort((a, b) => b.month.localeCompare(a.month) || a.name.localeCompare(b.name));
    return later(paginate(rows, query.page, query.pageSize));
  },
  async payslip(id) {
    return later(store().payslips.find((row) => row.id === id) ?? missing("Payslip"));
  },
  async summary(year) {
    const people = (await staffDirectory()).length;
    const months = Array.from({ length: 12 }, (_, index) => `${year}-${String(index + 1).padStart(2, "0")}`);
    const current = new Date().toISOString().slice(0, 7);
    return later(
      months
        .filter((month) => month <= current)
        .map((month) => {
          const slips = store().payslips.filter((row) => row.month === month);
          const processed = slips.filter((row) => row.status === "processed").length;
          const failed = slips.filter((row) => row.status === "failed").length;
          return { month, processed, failed, pending: slips.length ? Math.max(people - processed - failed, 0) : people, total_net: round(slips.filter((row) => row.status === "processed").reduce((sum, row) => sum + row.net, 0)) };
        })
        .reverse(),
    );
  },
};

export function payrollService(): PayrollService {
  return isOperationsLive("payroll") ? livePayroll : mockPayroll;
}
