/**
 * Fee arithmetic shared by the sample client and the pages: structure checks, concessions,
 * what each student owes per installment, and how a payment is split across installments.
 * Amounts are rupees with up to two decimals; every sum is rounded to paise.
 */
import type { Allocation, Concession, DueLine, FeeStructure, FeeStructureInput, InstallmentInput } from "@/lib/ops/types";

export function paise(value: number): number {
  return Math.round(value * 100) / 100;
}

export function structureProblems(input: Pick<FeeStructureInput, "name" | "session_year_id" | "class_id" | "items" | "installments" | "late_fee_per_day">): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!input.name.trim()) errors.name = "Enter a name.";
  if (!input.session_year_id) errors.session_year_id = "Choose an academic session.";
  if (!input.class_id) errors.class_id = "Choose a class.";
  if (input.items.length === 0) errors.items = "Add at least one fee.";
  const types = new Set<number>();
  input.items.forEach((item, index) => {
    if (!item.fee_type_id) errors[`items.${index}.fee_type_id`] = "Choose a fee type.";
    else if (types.has(item.fee_type_id)) errors[`items.${index}.fee_type_id`] = "This fee type is already in the structure.";
    types.add(item.fee_type_id);
    if (!(item.amount > 0)) errors[`items.${index}.amount`] = "Enter an amount above 0.";
  });
  if (!(input.late_fee_per_day >= 0)) errors.late_fee_per_day = "Late fee can't be negative.";
  const total = paise(input.items.reduce((sum, item) => sum + (item.amount || 0), 0));
  if (input.installments.length === 0) errors.installments = "Add at least one installment.";
  const dates = new Set<string>();
  input.installments.forEach((installment: InstallmentInput, index) => {
    if (!installment.name.trim()) errors[`installments.${index}.name`] = "Enter a name.";
    if (!/^\d{4}-\d{2}-\d{2}$/.test(installment.due_date)) errors[`installments.${index}.due_date`] = "Choose a due date.";
    else if (dates.has(installment.due_date)) errors[`installments.${index}.due_date`] = "Two installments are due on the same day.";
    dates.add(installment.due_date);
    if (!(installment.amount > 0)) errors[`installments.${index}.amount`] = "Enter an amount above 0.";
  });
  const planned = paise(input.installments.reduce((sum, installment) => sum + (installment.amount || 0), 0));
  if (!errors.installments && input.installments.length && Math.abs(planned - total) > 0.001) {
    errors.installments = `Installments add up to ₹${planned.toFixed(2)}, but the fees total ₹${total.toFixed(2)}.`;
  }
  return errors;
}

/** Splits a total into n installments; the last one takes any paise left over. */
export function splitEvenly(total: number, count: number): number[] {
  if (count <= 0) return [];
  const each = Math.floor((total / count) * 100) / 100;
  const amounts = Array.from({ length: count }, () => each);
  amounts[count - 1] = paise(total - each * (count - 1));
  return amounts;
}

/** The rupee value of a concession on a total. Percent concessions are capped at 100%; fixed ones at the total. */
export function concessionValue(total: number, concession: Pick<Concession, "kind" | "value"> | null | undefined): number {
  if (!concession) return 0;
  if (concession.kind === "percent") return paise((total * Math.min(Math.max(concession.value, 0), 100)) / 100);
  return paise(Math.min(Math.max(concession.value, 0), total));
}

/** Spreads a concession over installments in proportion to their amounts (the last one absorbs rounding). */
export function spreadConcession(amounts: number[], concession: number): number[] {
  const total = amounts.reduce((sum, amount) => sum + amount, 0);
  if (!total || !concession) return amounts.map(() => 0);
  let left = paise(concession);
  return amounts.map((amount, index) => {
    if (index === amounts.length - 1) return paise(left);
    const share = paise((amount / total) * concession);
    left = paise(left - share);
    return share;
  });
}

type Paid = { structure_id: number; installment_id: number; amount: number };

/**
 * What one student owes: every installment of every structure that applies to them, less any
 * concession, less what successful payments have covered.
 */
export function dueLines(structures: FeeStructure[], concessions: Pick<Concession, "structure_id" | "kind" | "value">[], paid: Paid[], today: string): DueLine[] {
  const lines: DueLine[] = [];
  for (const structure of structures) {
    const installments = [...structure.installments].sort((a, b) => a.due_date.localeCompare(b.due_date) || a.id - b.id);
    const concession = concessionValue(structure.total, concessions.find((item) => item.structure_id === structure.id));
    const shares = spreadConcession(installments.map((item) => item.amount), concession);
    installments.forEach((installment, index) => {
      const paidHere = paise(paid.filter((item) => item.structure_id === structure.id && item.installment_id === installment.id).reduce((sum, item) => sum + item.amount, 0));
      const balance = paise(Math.max(installment.amount - shares[index] - paidHere, 0));
      lines.push({
        structure_id: structure.id,
        structure_name: structure.name,
        installment_id: installment.id,
        installment_name: installment.name,
        due_date: installment.due_date,
        amount: installment.amount,
        concession: shares[index],
        paid: paidHere,
        balance,
        overdue: balance > 0 && installment.due_date < today,
      });
    });
  }
  return lines.sort((a, b) => a.due_date.localeCompare(b.due_date) || a.structure_id - b.structure_id);
}

export function totals(lines: DueLine[]) {
  const sum = (pick: (line: DueLine) => number) => paise(lines.reduce((total, line) => total + pick(line), 0));
  return {
    total: sum((line) => line.amount),
    concession: sum((line) => line.concession),
    paid: sum((line) => line.paid),
    balance: sum((line) => line.balance),
    overdue: sum((line) => (line.overdue ? line.balance : 0)),
  };
}

/**
 * Splits a payment across installments, earliest due first (partial payments leave the rest
 * on the next installment). Throws when the amount is above what's owed.
 */
export function allocate(amount: number, lines: DueLine[]): Allocation[] {
  const value = paise(amount);
  if (!(value > 0)) throw new RangeError("Enter an amount above 0.");
  const owed = paise(lines.reduce((sum, line) => sum + line.balance, 0));
  if (value > owed + 1e-9) throw new RangeError(`The student owes ₹${owed.toFixed(2)}; the payment can't be more than that.`);
  let left = value;
  const allocations: Allocation[] = [];
  for (const line of [...lines].sort((a, b) => a.due_date.localeCompare(b.due_date))) {
    if (left <= 0) break;
    if (line.balance <= 0) continue;
    const part = paise(Math.min(line.balance, left));
    allocations.push({ structure_id: line.structure_id, installment_id: line.installment_id, installment_name: line.installment_name, amount: part });
    left = paise(left - part);
  }
  return allocations;
}
