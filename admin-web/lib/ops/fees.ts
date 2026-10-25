/**
 * Student fees: fee types, fee structures with installments, extra assignments to students,
 * concessions/exemptions, what each student owes, payments and receipts.
 * Live (proposed, see backend/docs/FEES_TRANSPORT_GRADING_API_CONTRACT.md):
 *   /school-admin/fee-types, /fee-structures, /fee-assignments, /fee-concessions,
 *   /school-admin/students/{id}/fees, /fee-payments (POST needs an Idempotency-Key header),
 *   /fee-payments/{id}, /fee-payments/{id}/receipt, /fee-outstanding
 * Payments: office payments (cash, cheque, transfer, UPI or card at the counter) are recorded
 * by the server as successful; online payments stay "pending" until the server confirms them.
 * This client never marks a payment successful by itself.
 */
import { listAll } from "@/lib/academics";
import { peopleService } from "@/lib/people";
import { allocate, dueLines, paise, structureProblems, totals } from "@/lib/ops/fees-math";
import { studentRef } from "@/lib/ops/lookups";
import { isOpsLive } from "@/lib/ops/mode";
import { conflict, invalid, later, missing, nextId, opsDb, opsSave, today, type PaymentRow, type StructureRow } from "@/lib/ops/store";
import { FEE_CATEGORIES, PAYMENT_METHODS } from "@/lib/ops/types";
import type {
  Concession,
  ConcessionInput,
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
  PaymentQuery,
  Receipt,
  RecordStatus,
  StudentDues,
} from "@/lib/ops/types";
import { get, request, send } from "@/lib/teaching/client";
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

export const liveFees: FeeService = {
  async types() {
    return (await get<{ items?: FeeType[] }>("/school-admin/fee-types", { page_size: 50 }, "Unable to load fee types.")).items ?? [];
  },
  async saveType(input, id) {
    const problems = typeProblems(input);
    if (Object.keys(problems).length) invalid(problems);
    return id ? send<FeeType>("PATCH", `/school-admin/fee-types/${id}`, input, "Unable to save the fee type.") : send<FeeType>("POST", "/school-admin/fee-types", input, "Unable to add the fee type.");
  },
  async setTypeStatus(id, status) {
    return send<FeeType>("PATCH", `/school-admin/fee-types/${id}`, { status }, "Unable to change the fee type.");
  },
  async structures(query = {}) {
    return get<Page<FeeStructure>>("/school-admin/fee-structures", {
      page: query.page ?? 1,
      page_size: Math.min(query.pageSize ?? 20, 50),
      q: query.q?.trim(),
      session_year_id: query.sessionYearId,
      class_id: query.classId,
      status: query.status,
      sort: query.sort,
      order: query.order,
    }, "Unable to load fee structures.");
  },
  async getStructure(id) {
    return get<FeeStructure>(`/school-admin/fee-structures/${id}`, {}, "Unable to load the fee structure.");
  },
  async saveStructure(input, id) {
    const problems = structureProblems(input);
    if (Object.keys(problems).length) invalid(problems);
    return id ? send<FeeStructure>("PATCH", `/school-admin/fee-structures/${id}`, input, "Unable to save the fee structure.") : send<FeeStructure>("POST", "/school-admin/fee-structures", input, "Unable to add the fee structure.");
  },
  async setStructureStatus(id, status) {
    return send<FeeStructure>("PATCH", `/school-admin/fee-structures/${id}`, { status }, "Unable to change the fee structure.");
  },
  async assignments(structureId) {
    return (await get<{ items?: FeeAssignment[] }>("/school-admin/fee-assignments", { structure_id: structureId, page_size: 50 }, "Unable to load fee assignments.")).items ?? [];
  },
  async assign(structureId, studentId) {
    return send<FeeAssignment>("POST", "/school-admin/fee-assignments", { structure_id: structureId, student_id: studentId }, "Unable to assign the fees.");
  },
  async unassign(id) {
    await send("DELETE", `/school-admin/fee-assignments/${id}`, undefined, "Unable to remove the assignment.");
  },
  async concessions(structureId) {
    return (await get<{ items?: Concession[] }>("/school-admin/fee-concessions", { structure_id: structureId, page_size: 50 }, "Unable to load concessions.")).items ?? [];
  },
  async saveConcession(input, id) {
    const problems = concessionProblems(input);
    if (Object.keys(problems).length) invalid(problems);
    return id ? send<Concession>("PATCH", `/school-admin/fee-concessions/${id}`, input, "Unable to save the concession.") : send<Concession>("POST", "/school-admin/fee-concessions", input, "Unable to add the concession.");
  },
  async removeConcession(id) {
    await send("DELETE", `/school-admin/fee-concessions/${id}`, undefined, "Unable to remove the concession.");
  },
  async dues(studentId) {
    return get<StudentDues>(`/school-admin/students/${studentId}/fees`, {}, "Unable to load the student's fees.");
  },
  async recordPayment(input) {
    const { idempotency_key: key, ...body } = input;
    return request<FeePayment>(
      "/school-admin/fee-payments",
      { method: "POST", body: JSON.stringify(body), headers: { "Idempotency-Key": key } },
      "Unable to record the payment.",
    );
  },
  async payments(query = {}) {
    return get<Page<FeePayment>>("/school-admin/fee-payments", {
      page: query.page ?? 1,
      page_size: Math.min(query.pageSize ?? 20, 50),
      q: query.q?.trim(),
      student_id: query.studentId,
      class_section_id: query.classSectionId,
      method: query.method,
      status: query.status,
      from_date: query.from,
      to_date: query.to,
    }, "Unable to load payments.");
  },
  async payment(id) {
    return get<FeePayment>(`/school-admin/fee-payments/${id}`, {}, "Unable to load the payment.");
  },
  async receipt(id) {
    return get<Receipt>(`/school-admin/fee-payments/${id}/receipt`, {}, "Unable to load the receipt.");
  },
  async outstanding(query = {}) {
    return (await get<{ items?: StudentDues[] }>("/school-admin/fee-outstanding", {
      session_year_id: query.sessionYearId,
      class_id: query.classId,
      class_section_id: query.classSectionId,
      q: query.q?.trim(),
      due_before: query.dueBefore,
      only_overdue: query.onlyOverdue ? 1 : undefined,
      page_size: 50,
    }, "Unable to load outstanding fees.")).items ?? [];
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

export function feeService(): FeeService {
  return isOpsLive("fees") ? liveFees : mockFees;
}
