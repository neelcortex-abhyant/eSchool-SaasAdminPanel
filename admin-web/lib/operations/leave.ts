/**
 * Staff leave on the server's routes:
 *   GET/POST /school-admin/academics/leaves, PATCH /academics/leaves/{id} {status} (0 pending,
 *   1 approved, 2 rejected), DELETE /academics/leaves/{id}
 *   GET/PUT  /school-admin/leave-settings {policy, notes}
 * The server's leave has no type, so the type is kept at the start of the reason
 * ("Casual leave: fever") and read back from there. Leave types live in the leave settings
 * policy as `types`.
 */
import { listRows, getOne, replace, staffDirectory, type StaffRef } from "@/lib/extras/api";
import type { LeaveRequest, LeaveStatus, LeaveType } from "@/lib/operations/types";
import { num, send, str, type Raw } from "@/lib/teaching/client";
import { invalid } from "@/lib/ops/store";

export const LEAVE_STATUS: Record<LeaveStatus, string> = { 0: "Pending", 1: "Approved", 2: "Rejected" };

export const DEFAULT_LEAVE_TYPES: LeaveType[] = [
  { key: "casual", name: "Casual leave", days_per_year: 12, applies_to: "staff" },
  { key: "sick", name: "Sick leave", days_per_year: 10, applies_to: "staff" },
  { key: "earned", name: "Earned leave", days_per_year: 15, applies_to: "staff" },
  { key: "unpaid", name: "Unpaid leave", days_per_year: 0, applies_to: "staff" },
];

/** Leave types from the settings policy; older settings (day counts only) become types too. */
export function typesFromPolicy(policy: unknown): LeaveType[] {
  const value = (policy && typeof policy === "object" ? policy : {}) as Record<string, unknown>;
  if (Array.isArray(value.types)) {
    return (value.types as Raw[])
      .map((row) => ({
        key: str(row.key) || str(row.name).toLowerCase().replace(/[^a-z0-9]+/g, "_"),
        name: str(row.name),
        days_per_year: Math.max(0, num(row.days_per_year)),
        applies_to: (["staff", "student", "all"].includes(str(row.applies_to)) ? str(row.applies_to) : "staff") as LeaveType["applies_to"],
      }))
      .filter((row) => row.name);
  }
  const types = DEFAULT_LEAVE_TYPES.map((type) => ({ ...type }));
  if (typeof value.staff_casual_days === "number") types[0].days_per_year = value.staff_casual_days;
  if (typeof value.staff_sick_days === "number") types[1].days_per_year = value.staff_sick_days;
  return types;
}

/** "Casual leave: fever" → {type: "Casual leave", reason: "fever"} when the prefix is a known type. */
export function splitReason(text: string, types: LeaveType[]): { type: string | null; reason: string } {
  const at = text.indexOf(":");
  if (at > 0) {
    const name = text.slice(0, at).trim();
    if (types.some((type) => type.name.toLowerCase() === name.toLowerCase())) return { type: name, reason: text.slice(at + 1).trim() };
  }
  return { type: null, reason: text };
}

export function joinReason(type: string | null, reason: string): string {
  return type ? `${type}: ${reason.trim()}` : reason.trim();
}

/** Calendar days from `from` to `to`, both included. */
export function leaveDays(from: string, to: string): number {
  const start = new Date(`${from}T00:00:00`).getTime();
  const end = new Date(`${to}T00:00:00`).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return 0;
  return Math.round((end - start) / 86_400_000) + 1;
}

export type LeaveBalance = { type: LeaveType; allowed: number; used: number; pending: number; remaining: number };

/** Approved days of each type in a year against what the policy allows. Pending days are shown apart. */
export function balances(requests: LeaveRequest[], userId: number, types: LeaveType[], year: number): LeaveBalance[] {
  const mine = requests.filter((row) => row.user_id === userId && row.from_date.startsWith(String(year)));
  return types
    .filter((type) => type.applies_to !== "student")
    .map((type) => {
      const ofType = mine.filter((row) => (row.leave_type ?? "").toLowerCase() === type.name.toLowerCase());
      const used = ofType.filter((row) => row.status === 1).reduce((sum, row) => sum + row.days, 0);
      const pending = ofType.filter((row) => row.status === 0).reduce((sum, row) => sum + row.days, 0);
      return { type, allowed: type.days_per_year, used, pending, remaining: Math.max(type.days_per_year - used, 0) };
    });
}

export type LeaveSettings = { types: LeaveType[]; approval: string; notes: string; policy: Record<string, unknown> };

export async function loadLeaveSettings(): Promise<LeaveSettings> {
  const row = await getOne("/leave-settings");
  const policy = (row.policy && typeof row.policy === "object" && !Array.isArray(row.policy) ? row.policy : {}) as Record<string, unknown>;
  return { types: typesFromPolicy(policy), approval: str(policy.approval, "admin"), notes: str(row.notes), policy };
}

export function leaveTypeProblems(types: LeaveType[]): Record<string, string> {
  const errors: Record<string, string> = {};
  const names = new Set<string>();
  types.forEach((type, index) => {
    const name = type.name.trim().toLowerCase();
    if (!name) errors[`types.${index}`] = "Give the leave type a name.";
    else if (name.includes(":")) errors[`types.${index}`] = "A name can't contain “:”.";
    else if (names.has(name)) errors[`types.${index}`] = "Two leave types have this name.";
    else if (!(type.days_per_year >= 0) || type.days_per_year > 365) errors[`types.${index}`] = "Days per year must be 0–365.";
    names.add(name);
  });
  if (!types.length) errors.types = "Keep at least one leave type.";
  return errors;
}

/** Saves the types into the policy, keeping any other settings already there. */
export async function saveLeaveSettings(settings: Pick<LeaveSettings, "types" | "approval" | "notes" | "policy">): Promise<void> {
  const problems = leaveTypeProblems(settings.types);
  if (Object.keys(problems).length) invalid(problems);
  const types = settings.types.map((type) => ({ ...type, name: type.name.trim(), key: type.key || type.name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_") }));
  const casual = types.find((type) => type.key === "casual");
  const sick = types.find((type) => type.key === "sick");
  await replace("/leave-settings", {
    policy: {
      ...settings.policy,
      types,
      approval: settings.approval,
      // The older day-count settings stay in step for anything that still reads them.
      ...(casual ? { staff_casual_days: casual.days_per_year } : {}),
      ...(sick ? { staff_sick_days: sick.days_per_year } : {}),
    },
    notes: settings.notes.trim() || null,
  });
}

function kindOf(userId: number, people: StaffRef[]): LeaveRequest["kind"] {
  const person = people.find((row) => row.user_id === userId);
  return person ? person.kind : "unknown";
}

export async function loadLeaves(types: LeaveType[]): Promise<LeaveRequest[]> {
  const [rows, people] = await Promise.all([listRows("/academics/leaves"), staffDirectory()]);
  return rows
    .map((row): LeaveRequest => {
      const userId = num(row.user_id);
      const { type, reason } = splitReason(str(row.name ?? row.reason), types);
      const from = str(row.from_date).slice(0, 10);
      const to = str(row.to_date).slice(0, 10);
      return {
        id: num(row.id),
        user_id: userId,
        person_name: people.find((person) => person.user_id === userId)?.name ?? `User #${userId}`,
        kind: kindOf(userId, people),
        leave_type: type,
        reason,
        from_date: from,
        to_date: to,
        days: leaveDays(from, to),
        status: (num(row.status) === 1 ? 1 : num(row.status) === 2 ? 2 : 0) as LeaveStatus,
      };
    })
    .sort((a, b) => a.status - b.status || b.from_date.localeCompare(a.from_date));
}

export async function setLeaveStatus(id: number, status: LeaveStatus): Promise<void> {
  await send("PATCH", `/school-admin/academics/leaves/${id}`, { status }, status === 1 ? "Unable to approve the leave." : "Unable to reject the leave.");
}

export type LeaveInput = { user_id: number; leave_type: string; reason: string; from_date: string; to_date: string; session_year_id: number };

export function leaveProblems(input: LeaveInput): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!input.user_id) errors.user_id = "Choose the person.";
  if (!input.leave_type) errors.leave_type = "Choose the leave type.";
  if (!input.reason.trim()) errors.reason = "Enter the reason.";
  if (!input.from_date) errors.from_date = "Choose the first day.";
  if (!input.to_date) errors.to_date = "Choose the last day.";
  else if (input.from_date && input.to_date < input.from_date) errors.to_date = "The last day can't be before the first.";
  if (!input.session_year_id) errors.session_year_id = "Choose the academic session.";
  return errors;
}

export async function createLeave(input: LeaveInput): Promise<void> {
  const problems = leaveProblems(input);
  if (Object.keys(problems).length) invalid(problems);
  await send(
    "POST",
    "/school-admin/academics/leaves",
    { user_id: input.user_id, reason: joinReason(input.leave_type, input.reason), from_date: input.from_date, to_date: input.to_date, session_year_id: input.session_year_id, status: 0 },
    "Unable to add the leave.",
  );
}
