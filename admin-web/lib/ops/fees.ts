/**
 * Student fees: fee types, fee structures with installments, extra assignments to students,
 * concessions/exemptions, what each student owes, payments and receipts.
 * Live: /school-admin/fee-types, /fee-structures, /fee-assignments, /fee-concessions,
 *   /fee-payments, /fees/collect (idempotency_key in the body) and /fees/outstanding.
 *   The server has no installments, due dates or late fees: a student owes each structure
 *   assigned to them, paid in one or more parts. It has no per-student dues or receipt route,
 *   so those are worked out here from its lists, the same way the server does.
 * Payments: office payments (cash, cheque, transfer, UPI or card at the counter) are recorded
 * by the server as successful; online payments stay "pending" until the server confirms them.
 * This client never marks a payment successful by itself.
 */
import { listAll } from "@/lib/academics";
import { peopleService } from "@/lib/people";
import { allocate, concessionValue, dueLines, paise, structureProblems, totals } from "@/lib/ops/fees-math";
import { studentRef, studentRefs } from "@/lib/ops/lookups";
import { isOpsLive } from "@/lib/ops/mode";
import { conflict, invalid, later, missing, nextId, opsDb, opsSave, today, type PaymentRow, type StructureRow } from "@/lib/ops/store";
import { FEE_CATEGORIES, PAYMENT_METHODS } from "@/lib/ops/types";
import type {
  Concession,
  ConcessionInput,
  DueLine,
  FeeAssignment,
  FeeCategory,
  FeePayment,
  FeeStructure,
  FeeStructureInput,
  FeeStructureQuery,
  FeeType,
  FeeTypeInput,
  OutstandingQuery,
  Page,
  PaymentInput,
  PaymentMethod,
  PaymentQuery,
  PaymentStatus,
  Receipt,
  RecordStatus,
  StudentDues,
} from "@/lib/ops/types";
import { allPages, get, notAvailable, num, optNum, optStr, send, str, type Raw } from "@/lib/teaching/client";
import { academicsService } from "@/lib/academics";

export interface FeeService {
  types(): Promise<FeeType[]>;
  saveType(input: FeeTypeInput, id?: number): Promise<FeeType>;
  setTypeStatus(id: number, status: RecordStatus): Promise<FeeType>;
  structures(query?: FeeStructureQuery): Promise<Page<FeeStructure>>;
  getStructure(id: number): Promise<FeeStructure>;
  saveStructure(input: FeeStructureInput, id?: number): Promise<FeeStructure>;
  setStructureStatus(id: number, status: RecordStatus): Promise<FeeStructure>;
  assignments(structureId?: number): Promise<FeeAssignment[]>;
  assign(structureId: number, studentId: number): Promise<FeeAssignment>;
  unassign(id: number): Promise<void>;
  concessions(structureId?: number): Promise<Concession[]>;
  saveConcession(input: ConcessionInput, id?: number): Promise<Concession>;
  removeConcession(id: number): Promise<void>;
  dues(studentId: number): Promise<StudentDues>;
  recordPayment(input: PaymentInput): Promise<FeePayment>;
  payments(query?: PaymentQuery): Promise<Page<FeePayment>>;
  payment(id: number): Promise<FeePayment>;
  receipt(id: number): Promise<Receipt>;
  outstanding(query?: OutstandingQuery): Promise<StudentDues[]>;
}

// ---------- shared checks ----------

function typeProblems(input: FeeTypeInput): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!input.name.trim()) errors.name = "Enter a name.";
  if (!FEE_CATEGORIES.some((item) => item.value === input.category)) errors.category = "Choose a category.";
  return errors;
}

export function paymentProblems(input: Omit<PaymentInput, "idempotency_key">, balance: number): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!input.student_id) errors.student_id = "Choose a student.";
  if (!(input.amount > 0)) errors.amount = "Enter an amount above 0.";
  else if (paise(input.amount) > paise(balance) + 1e-9) errors.amount = `The student owes ₹${balance.toFixed(2)}; the payment can't be more than that.`;
  if (!PAYMENT_METHODS.some((item) => item.value === input.method)) errors.method = "Choose how the fee was paid.";
  if ((input.method === "cheque" || input.method === "bank_transfer" || input.method === "upi") && !input.reference?.trim()) {
    errors.reference = input.method === "cheque" ? "Enter the cheque number." : "Enter the transaction reference.";
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(input.paid_on)) errors.paid_on = "Choose the payment date.";
  else if (input.paid_on > today()) errors.paid_on = "The payment date can't be in the future.";
  return errors;
}

function concessionProblems(input: ConcessionInput): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!input.student_id) errors.student_id = "Choose a student.";
  if (!input.structure_id) errors.structure_id = "Choose a fee structure.";
  if (!(input.value > 0)) errors.value = "Enter a value above 0.";
  else if (input.kind === "percent" && input.value > 100) errors.value = "A percentage can't be more than 100.";
  if (!input.reason.trim()) errors.reason = "Give a reason; it appears on the student's fee record.";
  return errors;
}

// ---------- live ----------

const F = "/school-admin";

type ServerFees = { types: FeeType[]; structures: Raw[]; concessions: Raw[] };

function liveType(row: Raw): FeeType {
  const category = str(row.category, "other");
  return {
    id: num(row.id),
    name: str(row.name),
    category: (FEE_CATEGORIES.some((item) => item.value === category) ? category : "other") as FeeCategory,
    description: optStr(row.description),
    status: num(row.status ?? 1) === 0 ? 0 : 1,
  };
}

async function liveTypes(): Promise<FeeType[]> {
  return (await allPages(`${F}/fee-types`, {}, "Unable to load fee types.")).map(liveType);
}

async function classNames() {
  const [sessions, classes] = await Promise.all([
    listAll((page) => academicsService("sessions").listSessions({ page, pageSize: 50 })).catch(() => []),
    listAll((page) => academicsService("classes").listClasses({ page, pageSize: 50 })).catch(() => []),
  ]);
  return {
    session: (id: number) => sessions.find((row) => row.id === id)?.name ?? `Session #${id}`,
    klass: (id: number | null) => (id ? classes.find((row) => row.id === id)?.name ?? `Class #${id}` : "Any class"),
  };
}

/** The server's structure (amounts, no installments) in this app's shape. */
function liveStructure(row: Raw, types: FeeType[], names: Awaited<ReturnType<typeof classNames>>): FeeStructure {
  const amounts = Array.isArray(row.amounts) ? (row.amounts as Raw[]) : [];
  const items = amounts.map((item) => {
    const type = types.find((t) => t.id === num(item.fee_type_id));
    return { fee_type_id: num(item.fee_type_id), fee_type_name: type?.name ?? `Fee type #${num(item.fee_type_id)}`, category: type?.category ?? ("other" as FeeCategory), amount: paise(num(item.amount)) };
  });
  return {
    id: num(row.id),
    name: str(row.name),
    session_year_id: num(row.session_year_id),
    session_name: names.session(num(row.session_year_id)),
    class_id: num(row.class_id),
    class_name: names.klass(optNum(row.class_id)),
    items,
    installments: [],
    total: paise(items.reduce((sum, item) => sum + item.amount, 0)),
    late_fee_per_day: 0,
    status: num(row.status ?? 1) === 0 ? 0 : 1,
  };
}

async function liveStructures(): Promise<FeeStructure[]> {
  const [rows, types, names] = await Promise.all([allPages(`${F}/fee-structures`, {}, "Unable to load fee structures."), liveTypes(), classNames()]);
  return rows.map((row) => liveStructure(row, types, names));
}

function structureBody(input: FeeStructureInput) {
  return { name: input.name.trim(), session_year_id: input.session_year_id, class_id: input.class_id || null, amounts: input.items.map((item) => ({ fee_type_id: item.fee_type_id, amount: paise(item.amount) })), status: input.status };
}

/** The server has no installments, so a structure is checked without them. */
function liveStructureProblems(input: FeeStructureInput) {
  const total = paise(input.items.reduce((sum, item) => sum + (item.amount || 0), 0));
  const { installments: _i, late_fee_per_day: _l, ...rest } = structureProblems({ ...input, late_fee_per_day: 0, installments: [{ name: "Full", due_date: today(), amount: total || 1 }] });
  return rest;
}

const NO_DUE_DATE = "";

/** One line per fee structure assigned to the student, worked out the way the server does. */
async function liveDues(studentId: number): Promise<StudentDues> {
  const [student, assignments, structures, concessions, payments] = await Promise.all([
    studentRef(studentId),
    allPages(`${F}/fee-assignments`, { student_id: studentId }, "Unable to load the student's fees."),
    liveStructures(),
    allPages(`${F}/fee-concessions`, {}, "Unable to load concessions."),
    allPages(`${F}/fee-payments`, { student_id: studentId }, "Unable to load payments."),
  ]);
  const lines: DueLine[] = assignments.map((assignment) => {
    const structure = structures.find((row) => row.id === num(assignment.structure_id));
    const total = structure?.total ?? 0;
    const concessionRow = concessions.find((row) => num(row.student_id) === studentId && num(row.structure_id) === num(assignment.structure_id));
    const concession = concessionValue(total, concessionRow ? { kind: str(concessionRow.kind) === "percent" ? "percent" : "amount", value: num(concessionRow.value) } : null);
    const paid = paise(payments.filter((row) => num(row.assignment_id) === num(assignment.id) && str(row.status, "success") === "success").reduce((sum, row) => sum + num(row.amount), 0));
    return {
      structure_id: num(assignment.structure_id),
      structure_name: structure?.name ?? `Fee structure #${num(assignment.structure_id)}`,
      installment_id: num(assignment.id),
      installment_name: structure?.name ?? "Fees",
      due_date: NO_DUE_DATE,
      amount: total,
      concession,
      paid,
      balance: paise(Math.max(total - concession - paid, 0)),
      overdue: false,
    };
  });
  return {
    student_id: student.student_id,
    student_name: student.student_name,
    admission_no: student.admission_no,
    class_name: student.class_name,
    section_name: student.section_name,
    class_section_id: student.class_section_id,
    lines,
    ...totals(lines),
    pending: 0,
  };
}

function livePayment(row: Raw, student: Awaited<ReturnType<typeof studentRef>> | undefined, structures: FeeStructure[], assignments: Raw[]): FeePayment {
  const assignment = assignments.find((item) => num(item.id) === num(row.assignment_id));
  const structure = structures.find((item) => item.id === num(assignment?.structure_id));
  const method = str(row.method, "cash");
  return {
    id: num(row.id),
    receipt_no: optStr(row.receipt_no),
    student_id: num(row.student_id),
    student_name: student?.student_name ?? `Student #${num(row.student_id)}`,
    admission_no: student?.admission_no ?? "",
    class_name: student?.class_name ?? "",
    section_name: student?.section_name ?? "",
    amount: paise(num(row.amount)),
    method: (PAYMENT_METHODS.some((item) => item.value === method) ? method : "cash") as PaymentMethod,
    reference: optStr(row.reference),
    remarks: optStr(row.remarks),
    status: (["success", "pending", "failed"].includes(str(row.status)) ? str(row.status) : "success") as PaymentStatus,
    paid_at: optStr(row.paid_on) ? `${str(row.paid_on).slice(0, 10)}T${str(row.created_at).slice(11) || "00:00:00"}` : str(row.created_at),
    allocations: [{ structure_id: structure?.id ?? 0, installment_id: num(row.assignment_id), installment_name: structure?.name ?? "Fees", amount: paise(num(row.amount)) }],
    collected_by: null,
  };
}

async function livePayments(studentId?: number): Promise<FeePayment[]> {
  const [rows, structures, assignments] = await Promise.all([
    allPages(`${F}/fee-payments`, { student_id: studentId }, "Unable to load payments."),
    liveStructures(),
    allPages(`${F}/fee-assignments`, { student_id: studentId }, "Unable to load fee assignments."),
  ]);
  const students = await studentRefs(rows.map((row) => num(row.student_id)));
  return rows.map((row) => livePayment(row, students.get(num(row.student_id)), structures, assignments)).sort((a, b) => b.paid_at.localeCompare(a.paid_at) || b.id - a.id);
}

function pageSlice<T>(rows: T[], query: { page?: number; pageSize?: number }): Page<T> {
  const size = Math.min(query.pageSize ?? 20, 50);
  const page = Math.max(query.page ?? 1, 1);
  return { items: rows.slice((page - 1) * size, page * size), total: rows.length, page, page_size: size };
}

export const liveFees: FeeService = {
  async types() {
    return (await liveTypes()).sort((a, b) => b.status - a.status || a.name.localeCompare(b.name));
  },
  async saveType(input, id) {
    const problems = typeProblems(input);
    if (Object.keys(problems).length) invalid(problems);
    if ((await liveTypes()).some((row) => row.id !== id && row.name.trim().toLowerCase() === input.name.trim().toLowerCase())) conflict("A fee type with this name already exists.", "name");
    const body = { name: input.name.trim(), category: input.category, description: input.description?.trim() || null, status: input.status };
    return liveType(id ? await send("PATCH", `${F}/fee-types/${id}`, body, "Unable to save the fee type.") : await send("POST", `${F}/fee-types`, body, "Unable to add the fee type."));
  },
  async setTypeStatus(id, status) {
    return liveType(await send("PATCH", `${F}/fee-types/${id}`, { status }, "Unable to change the fee type."));
  },
  async structures(query = {}) {
    const needle = query.q?.trim().toLowerCase() ?? "";
    const sorters: Record<string, (row: FeeStructure) => string | number> = { name: (row) => row.name.toLowerCase(), class: (row) => row.class_name, total: (row) => row.total };
    const sorter = sorters[query.sort ?? "name"];
    const order = query.order === "desc" ? -1 : 1;
    const rows = (await liveStructures())
      .filter((row) => !query.sessionYearId || row.session_year_id === query.sessionYearId)
      .filter((row) => !query.classId || row.class_id === query.classId)
      .filter((row) => (query.status === "0" || query.status === "1" ? String(row.status) === query.status : true))
      .filter((row) => !needle || row.name.toLowerCase().includes(needle) || row.items.some((item) => item.fee_type_name.toLowerCase().includes(needle)))
      .sort((a, b) => {
        const x = sorter(a);
        const y = sorter(b);
        return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true })) * order || a.id - b.id;
      });
    return pageSlice(rows, query);
  },
  async getStructure(id) {
    const [row, types, names] = await Promise.all([get(`${F}/fee-structures/${id}`, {}, "Unable to load the fee structure."), liveTypes(), classNames()]);
    return liveStructure(row, types, names);
  },
  async saveStructure(input, id) {
    const problems = liveStructureProblems(input);
    if (Object.keys(problems).length) invalid(problems);
    const [types, names] = await Promise.all([liveTypes(), classNames()]);
    const row = id ? await send("PATCH", `${F}/fee-structures/${id}`, structureBody(input), "Unable to save the fee structure.") : await send("POST", `${F}/fee-structures`, structureBody(input), "Unable to add the fee structure.");
    return liveStructure(row, types, names);
  },
  async setStructureStatus(id, status) {
    const [row, types, names] = await Promise.all([send("PATCH", `${F}/fee-structures/${id}`, { status }, "Unable to change the fee structure."), liveTypes(), classNames()]);
    return liveStructure(row, types, names);
  },
  async assignments(structureId) {
    const [rows, structures] = await Promise.all([allPages(`${F}/fee-assignments`, { structure_id: structureId }, "Unable to load fee assignments."), liveStructures()]);
    const students = await studentRefs(rows.map((row) => num(row.student_id)));
    return rows
      .map((row) => {
        const student = students.get(num(row.student_id));
        return {
          id: num(row.id),
          structure_id: num(row.structure_id),
          structure_name: structures.find((item) => item.id === num(row.structure_id))?.name ?? "",
          student_id: num(row.student_id),
          student_name: student?.student_name ?? `Student #${num(row.student_id)}`,
          admission_no: student?.admission_no ?? "",
        };
      })
      .sort((a, b) => a.student_name.localeCompare(b.student_name));
  },
  async assign(structureId, studentId) {
    const existing = await allPages(`${F}/fee-assignments`, { structure_id: structureId, student_id: studentId }, "Unable to load fee assignments.");
    if (existing.length) conflict("This student already has these fees.", "student_id");
    const row = await send("POST", `${F}/fee-assignments`, { structure_id: structureId, student_id: studentId }, "Unable to assign the fees.");
    const [student, structure] = await Promise.all([studentRef(studentId), liveFees.getStructure(structureId)]);
    return { id: num(row.id), structure_id: structureId, structure_name: structure.name, student_id: studentId, student_name: student.student_name, admission_no: student.admission_no };
  },
  async unassign(id) {
    if ((await allPages(`${F}/fee-payments`, {}, "Unable to load payments.")).some((row) => num(row.assignment_id) === id && str(row.status, "success") === "success")) {
      conflict("Payments have been recorded against these fees, so the assignment can't be removed.");
    }
    await send("DELETE", `${F}/fee-assignments/${id}`, undefined, "Unable to remove the assignment.");
  },
  async concessions(structureId) {
    const [rows, structures] = await Promise.all([allPages(`${F}/fee-concessions`, {}, "Unable to load concessions."), liveStructures()]);
    const mine = rows.filter((row) => !structureId || num(row.structure_id) === structureId);
    const students = await studentRefs(mine.map((row) => num(row.student_id)));
    return mine
      .map((row): Concession => ({
        id: num(row.id),
        student_id: num(row.student_id),
        student_name: students.get(num(row.student_id))?.student_name ?? `Student #${num(row.student_id)}`,
        structure_id: num(row.structure_id),
        structure_name: structures.find((item) => item.id === num(row.structure_id))?.name ?? "",
        kind: str(row.kind) === "percent" ? "percent" : "amount",
        value: num(row.value),
        reason: str(row.reason),
      }))
      .sort((a, b) => a.student_name.localeCompare(b.student_name));
  },
  async saveConcession(input, id) {
    if (id) return notAvailable("The server can't edit a concession yet. Remove it and add it again.");
    const problems = concessionProblems(input);
    if (Object.keys(problems).length) invalid(problems);
    const rows = await allPages(`${F}/fee-concessions`, {}, "Unable to load concessions.");
    if (rows.some((row) => num(row.student_id) === input.student_id && num(row.structure_id) === input.structure_id)) {
      conflict("This student already has a concession on this structure. Remove that one first.", "student_id");
    }
    const row = await send("POST", `${F}/fee-concessions`, { student_id: input.student_id, structure_id: input.structure_id, kind: input.kind, value: input.value, reason: input.reason.trim() }, "Unable to add the concession.");
    const [student, structure] = await Promise.all([studentRef(input.student_id), liveFees.getStructure(input.structure_id)]);
    return { id: num(row.id), student_id: input.student_id, student_name: student.student_name, structure_id: input.structure_id, structure_name: structure.name, kind: input.kind, value: input.value, reason: input.reason.trim() };
  },
  async removeConcession(id) {
    await send("DELETE", `${F}/fee-concessions/${id}`, undefined, "Unable to remove the concession.");
  },
  async dues(studentId) {
    return liveDues(studentId);
  },
  async recordPayment(input) {
    if (!PAYMENT_METHODS.find((item) => item.value === input.method)?.manual) invalid({ method: "Online payment links aren't available on the server yet." });
    const dues = await liveDues(input.student_id);
    const problems = paymentProblems(input, dues.balance);
    if (Object.keys(problems).length) invalid(problems);
    let allocations;
    try {
      allocations = allocate(input.amount, dues.lines);
    } catch (caught) {
      invalid({ amount: caught instanceof Error ? caught.message : "The amount can't be allocated." });
    }
    // The server records a payment against one assigned structure, so a payment that covers
    // several is sent as one request per structure. Each has its own key, derived from the
    // form's, so a retry can't record any part twice.
    const saved: Raw[] = [];
    for (const allocation of allocations) {
      saved.push(
        await send("POST", `${F}/fees/collect`, {
          assignment_id: allocation.installment_id,
          amount: allocation.amount,
          method: input.method,
          reference: input.reference?.trim() || null,
          remarks: input.remarks?.trim() || null,
          paid_on: input.paid_on,
          idempotency_key: `${input.idempotency_key}:${allocation.installment_id}`,
        }, "Unable to record the payment."),
      );
    }
    const student = await studentRef(input.student_id);
    const first = saved[0];
    return {
      id: num(first.id),
      receipt_no: saved.map((row) => optStr(row.receipt_no)).filter(Boolean).join(", ") || null,
      student_id: student.student_id,
      student_name: student.student_name,
      admission_no: student.admission_no,
      class_name: student.class_name,
      section_name: student.section_name,
      amount: paise(input.amount),
      method: input.method,
      reference: input.reference?.trim() || null,
      remarks: input.remarks?.trim() || null,
      status: "success",
      paid_at: `${input.paid_on}T${str(first.created_at).slice(11) || "00:00:00"}`,
      allocations,
      collected_by: null,
    };
  },
  async payments(query = {}) {
    const needle = query.q?.trim().toLowerCase() ?? "";
    const all = await livePayments(query.studentId || undefined);
    const sections = query.classSectionId ? await studentRefs(all.map((row) => row.student_id)) : null;
    const rows = all
      .filter((row) => !sections || sections.get(row.student_id)?.class_section_id === query.classSectionId)
      .filter((row) => !query.method || row.method === query.method)
      .filter((row) => !query.status || row.status === query.status)
      .filter((row) => !query.from || row.paid_at.slice(0, 10) >= query.from)
      .filter((row) => !query.to || row.paid_at.slice(0, 10) <= query.to)
      .filter((row) => !needle || [row.student_name, row.admission_no, row.receipt_no ?? "", row.reference ?? ""].some((value) => value.toLowerCase().includes(needle)));
    return pageSlice(rows, query);
  },
  async payment(id) {
    return (await livePayments()).find((row) => row.id === id) ?? missing("Payment");
  },
  async receipt(id) {
    const payment = await liveFees.payment(id);
    const [dues, school, all] = await Promise.all([
      liveDues(payment.student_id),
      get("/school-admin/school", {}, "Unable to load the school.").catch(() => ({}) as Raw),
      livePayments(payment.student_id),
    ]);
    // Balance right after this payment: today's balance plus anything paid later.
    const paidLater = all.filter((p) => p.status === "success" && (p.paid_at > payment.paid_at || (p.paid_at === payment.paid_at && p.id > payment.id))).reduce((sum, p) => sum + p.amount, 0);
    const structure = dues.lines.find((line) => line.installment_id === payment.allocations[0]?.installment_id);
    return { payment, school_name: str(school.name, "School"), session_name: structure?.structure_name ?? "", balance_after: paise(dues.balance + paidLater) };
  },
  async outstanding(query = {}) {
    const [rows, structures] = await Promise.all([allPages(`${F}/fees/outstanding`, {}, "Unable to load outstanding fees."), liveStructures()]);
    const students = await studentRefs(rows.map((row) => num(row.student_id)));
    const needle = query.q?.trim().toLowerCase() ?? "";
    const byStudent = new Map<number, StudentDues>();
    for (const row of rows) {
      const student = students.get(num(row.student_id));
      if (!student) continue;
      const structure = structures.find((item) => item.id === num(row.structure_id));
      const concession = paise(num(row.concession));
      const line: DueLine = {
        structure_id: num(row.structure_id),
        structure_name: structure?.name ?? `Fee structure #${num(row.structure_id)}`,
        installment_id: num(row.assignment_id),
        installment_name: structure?.name ?? "Fees",
        due_date: NO_DUE_DATE,
        amount: paise(num(row.payable) + concession),
        concession,
        paid: paise(num(row.paid)),
        balance: paise(num(row.balance)),
        overdue: false,
      };
      const current = byStudent.get(student.student_id) ?? {
        student_id: student.student_id,
        student_name: student.student_name,
        admission_no: student.admission_no,
        class_name: student.class_name,
        section_name: student.section_name,
        class_section_id: student.class_section_id,
        lines: [],
        total: 0,
        concession: 0,
        paid: 0,
        balance: 0,
        overdue: 0,
        pending: 0,
      };
      const lines = [...current.lines, line];
      byStudent.set(student.student_id, { ...current, lines, ...totals(lines) });
    }
    return [...byStudent.values()]
      .filter((row) => {
        const student = students.get(row.student_id);
        return (
          (!query.sessionYearId || student?.session_year_id === query.sessionYearId) &&
          (!query.classId || student?.class_id === query.classId) &&
          (!query.classSectionId || row.class_section_id === query.classSectionId) &&
          (!needle || row.student_name.toLowerCase().includes(needle) || row.admission_no.toLowerCase().includes(needle))
        );
      })
      .sort((a, b) => b.balance - a.balance);
  },
};

// ---------- sample data ----------

function typeOut(row: { id: number; name: string; category: string; description: string | null; status: RecordStatus }): FeeType {
  return { ...row, category: row.category as FeeCategory };
}

function structureOut(row: StructureRow): FeeStructure {
  const types = opsDb().feeTypes;
  const items = row.items.map((item) => {
    const type = types.find((t) => t.id === item.fee_type_id);
    return { fee_type_id: item.fee_type_id, fee_type_name: type?.name ?? `Fee type #${item.fee_type_id}`, category: (type?.category ?? "other") as FeeCategory, amount: item.amount };
  });
  return { ...row, items, installments: [...row.installments].sort((a, b) => a.due_date.localeCompare(b.due_date)), total: paise(items.reduce((sum, item) => sum + item.amount, 0)) };
}

async function classInfo(sessionYearId: number, classId: number) {
  const [sessions, classes] = await Promise.all([
    listAll((page) => academicsService("sessions").listSessions({ page, pageSize: 50 })).catch(() => []),
    listAll((page) => academicsService("classes").listClasses({ page, pageSize: 50 })).catch(() => []),
  ]);
  return {
    session_name: sessions.find((row) => row.id === sessionYearId)?.name ?? `Session #${sessionYearId}`,
    class_name: classes.find((row) => row.id === classId)?.name ?? `Class #${classId}`,
  };
}

function paymentOut(row: PaymentRow): FeePayment {
  const { idempotency_key: _key, class_section_id: _cs, ...rest } = row;
  return rest;
}

/** Structures that apply to a student: their class's structures plus ones assigned to them. */
function structuresFor(studentId: number, classId: number, sessionYearId: number): FeeStructure[] {
  const db = opsDb();
  const extra = new Set(db.feeAssignments.filter((row) => row.student_id === studentId).map((row) => row.structure_id));
  return db.structures
    .filter((row) => row.status === 1 && row.session_year_id === sessionYearId && (row.class_id === classId || extra.has(row.id)))
    .map(structureOut);
}

async function mockDues(studentId: number): Promise<StudentDues> {
  const student = await studentRef(studentId);
  return duesFor(student);
}

function duesFor(student: Awaited<ReturnType<typeof studentRef>>): StudentDues {
  const db = opsDb();
  const structures = structuresFor(student.student_id, student.class_id, student.session_year_id);
  const mine = db.payments.filter((row) => row.student_id === student.student_id);
  const paid = mine.filter((row) => row.status === "success").flatMap((row) => row.allocations);
  const lines = dueLines(structures, db.concessions.filter((row) => row.student_id === student.student_id), paid, today());
  const sums = totals(lines);
  return {
    student_id: student.student_id,
    student_name: student.student_name,
    admission_no: student.admission_no,
    class_name: student.class_name,
    section_name: student.section_name,
    class_section_id: student.class_section_id,
    lines,
    ...sums,
    pending: paise(mine.filter((row) => row.status === "pending").reduce((sum, row) => sum + row.amount, 0)),
  };
}

export const mockFees: FeeService = {
  async types() {
    return later(opsDb().feeTypes.map(typeOut).sort((a, b) => b.status - a.status || a.name.localeCompare(b.name)));
  },
  async saveType(input, id) {
    const problems = typeProblems(input);
    if (Object.keys(problems).length) invalid(problems);
    const db = opsDb();
    if (db.feeTypes.some((row) => row.id !== id && row.name.trim().toLowerCase() === input.name.trim().toLowerCase())) conflict("A fee type with this name already exists.", "name");
    const row = { id: id ?? nextId(db.feeTypes), name: input.name.trim(), category: input.category, description: input.description?.trim() || null, status: input.status };
    const index = db.feeTypes.findIndex((item) => item.id === id);
    if (id && index < 0) missing("Fee type");
    if (index >= 0) db.feeTypes[index] = row;
    else db.feeTypes.push(row);
    opsSave();
    return later(typeOut(row));
  },
  async setTypeStatus(id, status) {
    const row = opsDb().feeTypes.find((item) => item.id === id) ?? missing("Fee type");
    row.status = status;
    opsSave();
    return later(typeOut(row));
  },
  async structures(query = {}) {
    const needle = query.q?.trim().toLowerCase() ?? "";
    const sorters: Record<string, (row: FeeStructure) => string | number> = { name: (row) => row.name.toLowerCase(), class: (row) => row.class_name, total: (row) => row.total };
    const sorter = sorters[query.sort ?? "name"];
    const order = query.order === "desc" ? -1 : 1;
    const rows = opsDb()
      .structures.map(structureOut)
      .filter((row) => !query.sessionYearId || row.session_year_id === query.sessionYearId)
      .filter((row) => !query.classId || row.class_id === query.classId)
      .filter((row) => (query.status === "0" || query.status === "1" ? String(row.status) === query.status : true))
      .filter((row) => !needle || row.name.toLowerCase().includes(needle) || row.items.some((item) => item.fee_type_name.toLowerCase().includes(needle)))
      .sort((a, b) => {
        const x = sorter(a);
        const y = sorter(b);
        return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true })) * order || a.id - b.id;
      });
    const size = Math.min(query.pageSize ?? 20, 50);
    const page = Math.max(query.page ?? 1, 1);
    return later({ items: rows.slice((page - 1) * size, page * size), total: rows.length, page, page_size: size });
  },
  async getStructure(id) {
    return later(structureOut(opsDb().structures.find((row) => row.id === id) ?? missing("Fee structure")));
  },
  async saveStructure(input, id) {
    const problems = structureProblems(input);
    if (Object.keys(problems).length) invalid(problems);
    const db = opsDb();
    if (db.structures.some((row) => row.id !== id && row.name.trim().toLowerCase() === input.name.trim().toLowerCase() && row.session_year_id === input.session_year_id)) {
      conflict("A fee structure with this name already exists in this session.", "name");
    }
    const existing = id ? db.structures.find((row) => row.id === id) ?? missing("Fee structure") : null;
    // Installments that already have payments against them can't be removed or reduced below what was paid.
    if (existing) {
      const paidByInstallment = new Map<number, number>();
      db.payments.filter((row) => row.status === "success").flatMap((row) => row.allocations).filter((a) => a.structure_id === existing.id).forEach((a) => paidByInstallment.set(a.installment_id, (paidByInstallment.get(a.installment_id) ?? 0) + a.amount));
      for (const [installmentId] of paidByInstallment) {
        if (!input.installments.some((item) => item.id === installmentId)) conflict("An installment with payments against it can't be removed. Change its amount or date instead.", "installments");
      }
    }
    let installmentId = Math.max(0, ...db.structures.flatMap((row) => row.installments.map((item) => item.id)));
    const names = await classInfo(input.session_year_id, input.class_id);
    const row: StructureRow = {
      id: existing?.id ?? nextId(db.structures),
      name: input.name.trim(),
      session_year_id: input.session_year_id,
      class_id: input.class_id,
      ...names,
      items: input.items.map((item) => ({ fee_type_id: item.fee_type_id, amount: paise(item.amount) })),
      installments: input.installments.map((item) => ({ id: item.id ?? (installmentId += 1), name: item.name.trim(), due_date: item.due_date, amount: paise(item.amount) })),
      late_fee_per_day: input.late_fee_per_day,
      status: input.status,
    };
    if (existing) db.structures[db.structures.indexOf(existing)] = row;
    else db.structures.push(row);
    opsSave();
    return later(structureOut(row));
  },
  async setStructureStatus(id, status) {
    const row = opsDb().structures.find((item) => item.id === id) ?? missing("Fee structure");
    row.status = status;
    opsSave();
    return later(structureOut(row));
  },
  async assignments(structureId) {
    const db = opsDb();
    return later(
      db.feeAssignments
        .filter((row) => !structureId || row.structure_id === structureId)
        .map((row) => ({ ...row, structure_name: db.structures.find((s) => s.id === row.structure_id)?.name ?? "" }))
        .sort((a, b) => a.student_name.localeCompare(b.student_name)),
    );
  },
  async assign(structureId, studentId) {
    const db = opsDb();
    const structure = db.structures.find((row) => row.id === structureId) ?? missing("Fee structure");
    if (db.feeAssignments.some((row) => row.structure_id === structureId && row.student_id === studentId)) conflict("This student already has these fees.", "student_id");
    const student = await studentRef(studentId);
    if (student.class_id === structure.class_id && student.session_year_id === structure.session_year_id) conflict(`${student.student_name} already pays this structure through their class.`, "student_id");
    const { class_id: _c, session_year_id: _s, ...ref } = student;
    const row = { id: nextId(db.feeAssignments), structure_id: structureId, ...ref };
    db.feeAssignments.push(row);
    opsSave();
    return later({ ...row, structure_name: structure.name });
  },
  async unassign(id) {
    const db = opsDb();
    const row = db.feeAssignments.find((item) => item.id === id) ?? missing("Fee assignment");
    const paid = db.payments.some((payment) => payment.student_id === row.student_id && payment.status === "success" && payment.allocations.some((a) => a.structure_id === row.structure_id));
    if (paid) conflict("Payments have been recorded against these fees, so the assignment can't be removed.");
    db.feeAssignments = db.feeAssignments.filter((item) => item.id !== id);
    opsSave();
    await later(null);
  },
  async concessions(structureId) {
    const db = opsDb();
    return later(
      db.concessions
        .filter((row) => !structureId || row.structure_id === structureId)
        .map((row) => ({ ...row, structure_name: db.structures.find((s) => s.id === row.structure_id)?.name ?? "" }))
        .sort((a, b) => a.student_name.localeCompare(b.student_name)),
    );
  },
  async saveConcession(input, id) {
    const problems = concessionProblems(input);
    if (Object.keys(problems).length) invalid(problems);
    const db = opsDb();
    const structure = db.structures.find((row) => row.id === input.structure_id) ?? missing("Fee structure");
    if (db.concessions.some((row) => row.id !== id && row.student_id === input.student_id && row.structure_id === input.structure_id)) {
      conflict("This student already has a concession on this structure. Edit that one instead.", "student_id");
    }
    const student = await studentRef(input.student_id);
    const { class_id: _c, session_year_id: _s, ...ref } = student;
    const row = { id: id ?? nextId(db.concessions), ...ref, structure_id: input.structure_id, kind: input.kind, value: input.value, reason: input.reason.trim() };
    const index = db.concessions.findIndex((item) => item.id === id);
    if (index >= 0) db.concessions[index] = row;
    else db.concessions.push(row);
    opsSave();
    return later({ ...row, structure_name: structure.name });
  },
  async removeConcession(id) {
    const db = opsDb();
    if (!db.concessions.some((item) => item.id === id)) missing("Concession");
    db.concessions = db.concessions.filter((item) => item.id !== id);
    opsSave();
    await later(null);
  },
  async dues(studentId) {
    return later(await mockDues(studentId));
  },
  async recordPayment(input) {
    const db = opsDb();
    // A retried request with the same key returns the payment already recorded.
    const repeat = db.payments.find((row) => row.idempotency_key === input.idempotency_key);
    if (repeat) return later(paymentOut(repeat));
    const student = await studentRef(input.student_id);
    const dues = duesFor(student);
    const problems = paymentProblems(input, dues.balance);
    if (Object.keys(problems).length) invalid(problems);
    let allocations;
    try {
      allocations = allocate(input.amount, dues.lines);
    } catch (caught) {
      invalid({ amount: caught instanceof Error ? caught.message : "The amount can't be allocated." });
    }
    const online = !PAYMENT_METHODS.find((item) => item.value === input.method)?.manual;
    const status = online ? "pending" : "success";
    const year = input.paid_on.slice(0, 4);
    const issued = db.payments.filter((row) => row.receipt_no?.startsWith(`RCPT-${year}-`)).length;
    const row: PaymentRow = {
      id: nextId(db.payments),
      receipt_no: status === "success" ? `RCPT-${year}-${String(issued + 1).padStart(4, "0")}` : null,
      student_id: student.student_id,
      student_name: student.student_name,
      admission_no: student.admission_no,
      class_name: student.class_name,
      section_name: student.section_name,
      class_section_id: student.class_section_id,
      amount: paise(input.amount),
      method: input.method,
      reference: input.reference?.trim() || null,
      remarks: input.remarks?.trim() || null,
      status,
      paid_at: `${input.paid_on}T${new Date().toISOString().slice(11)}`,
      allocations,
      collected_by: online ? null : "School admin",
      idempotency_key: input.idempotency_key,
    };
    db.payments.push(row);
    opsSave();
    return later(paymentOut(row));
  },
  async payments(query = {}) {
    const needle = query.q?.trim().toLowerCase() ?? "";
    const rows = opsDb()
      .payments.filter((row) => !query.studentId || row.student_id === query.studentId)
      .filter((row) => !query.classSectionId || row.class_section_id === query.classSectionId)
      .filter((row) => !query.method || row.method === query.method)
      .filter((row) => !query.status || row.status === query.status)
      .filter((row) => !query.from || row.paid_at.slice(0, 10) >= query.from)
      .filter((row) => !query.to || row.paid_at.slice(0, 10) <= query.to)
      .filter((row) => !needle || [row.student_name, row.admission_no, row.receipt_no ?? "", row.reference ?? ""].some((value) => value.toLowerCase().includes(needle)))
      .sort((a, b) => b.paid_at.localeCompare(a.paid_at) || b.id - a.id)
      .map(paymentOut);
    const size = Math.min(query.pageSize ?? 20, 50);
    const page = Math.max(query.page ?? 1, 1);
    return later({ items: rows.slice((page - 1) * size, page * size), total: rows.length, page, page_size: size });
  },
  async payment(id) {
    return later(paymentOut(opsDb().payments.find((row) => row.id === id) ?? missing("Payment")));
  },
  async receipt(id) {
    const row = opsDb().payments.find((item) => item.id === id) ?? missing("Payment");
    if (row.status !== "success") conflict("A receipt is issued only after the payment is confirmed.");
    const dues = await mockDues(row.student_id);
    // Balance right after this payment: today's balance plus anything paid later.
    const later_paid = opsDb().payments.filter((p) => p.student_id === row.student_id && p.status === "success" && (p.paid_at > row.paid_at || (p.paid_at === row.paid_at && p.id > row.id))).reduce((sum, p) => sum + p.amount, 0);
    return later({ payment: paymentOut(row), school_name: "Sample School", session_name: opsDb().structures[0]?.session_name ?? "", balance_after: paise(dues.balance + later_paid) });
  },
  async outstanding(query = {}) {
    const students = await listAll((page) =>
      peopleService("students").listStudents({ page, pageSize: 50, sessionYearId: query.sessionYearId, classId: query.classId, classSectionId: query.classSectionId, q: query.q, status: "1" }),
    );
    const rows = students.map((student) =>
      duesFor({
        student_id: student.id,
        student_name: student.name,
        admission_no: student.admission_no,
        class_section_id: student.class_section_id,
        class_name: student.class_name,
        section_name: student.section_name,
        class_id: student.class_id,
        session_year_id: student.session_year_id,
      }),
    );
    return later(
      rows
        .map((row) => (query.dueBefore ? { ...row, lines: row.lines.filter((line) => line.due_date <= (query.dueBefore as string)) } : row))
        .map((row) => (query.dueBefore ? { ...row, ...totals(row.lines) } : row))
        .filter((row) => row.total > 0)
        .filter((row) => !query.onlyOverdue || row.overdue > 0)
        .sort((a, b) => b.overdue - a.overdue || b.balance - a.balance),
    );
  },
};

/** Checks for the fee structure form: without installments when the server keeps none. */
export function structureFormProblems(input: FeeStructureInput): Record<string, string> {
  return isOpsLive("fees") ? liveStructureProblems(input) : structureProblems(input);
}

export function feeService(): FeeService {
  return isOpsLive("fees") ? liveFees : mockFees;
}
