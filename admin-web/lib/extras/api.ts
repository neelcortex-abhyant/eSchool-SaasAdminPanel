/**
 * Requests for the school-admin modules added in backend 0039 (admissions, notices, diaries,
 * holidays, online classes, website content, finance, payroll, certificates, ID cards, staff
 * attendance and tasks, reports, semesters/streams/shifts/syllabi, student actions).
 * Paths are relative to /api/v1/school-admin. These pages always call the server: the routes
 * exist on every deployment from 0039 on, so there is no sample-data mode.
 */
import { allPages, get, num, optNum, request, send, str, type Raw } from "@/lib/teaching/client";

export const SA = "/school-admin";

export type { Raw };

export function listRows(path: string, params: Record<string, string | number | undefined> = {}): Promise<Raw[]> {
  return allPages(`${SA}${path}`, params, "Unable to load the list.");
}

export function getOne(path: string, params: Record<string, string | number | undefined> = {}): Promise<Raw> {
  return get(`${SA}${path}`, params, "Unable to load this page.");
}

export function create(path: string, body: Raw): Promise<Raw> {
  return send("POST", `${SA}${path}`, body, "Unable to save.");
}

export function update(path: string, body: Raw): Promise<Raw> {
  return send("PATCH", `${SA}${path}`, body, "Unable to save the changes.");
}

export function replace(path: string, body: Raw): Promise<Raw> {
  return request<Raw>(`${SA}${path}`, { method: "PUT", body: JSON.stringify(body) }, "Unable to save the settings.");
}

export async function remove(path: string): Promise<void> {
  await send("DELETE", `${SA}${path}`, undefined, "Unable to delete.");
}

export type StaffRef = { staff_id: number; user_id: number; name: string; designation: string; kind: "teacher" | "staff"; salary?: number; employee_code?: string; department?: string };

/**
 * Teachers and other staff keyed by their staff record id, which attendance, tasks, payroll and
 * ID cards use (the people pages use the user id).
 */
export async function staffDirectory(): Promise<StaffRef[]> {
  const [staff, teachers] = await Promise.all([
    allPages(`${SA}/staff`, {}, "Unable to load staff.").catch(() => [] as Raw[]),
    allPages(`${SA}/teachers`, {}, "Unable to load teachers.").catch(() => [] as Raw[]),
  ]);
  const ref = (row: Raw, kind: StaffRef["kind"]): StaffRef | null => {
    const staffId = optNum(row.staff_id);
    if (!staffId) return null;
    const name = str(row.name) || `${str(row.first_name)} ${str(row.last_name)}`.trim();
    return { staff_id: staffId, user_id: num(row.id), name: name || `Staff #${staffId}`, designation: str(row.designation) || (kind === "teacher" ? "Teacher" : ""), kind, salary: num(row.salary ?? 0), employee_code: str(row.employee_id ?? row.employee_code), department: str(row.department) };
  };
  const rows = [...teachers.map((row) => ref(row, "teacher")), ...staff.map((row) => ref(row, "staff"))].filter((row): row is StaffRef => row !== null);
  const seen = new Set<number>();
  return rows.filter((row) => (seen.has(row.staff_id) ? false : (seen.add(row.staff_id), true))).sort((a, b) => a.name.localeCompare(b.name));
}

/** "2026-10-27T09:30:00" → "27 Oct 2026, 09:30"; dates alone stay as dates. */
export function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  const text = String(value);
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(text)) {
    const date = new Date(text);
    if (!Number.isNaN(date.getTime())) return `${date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}, ${text.slice(11, 16)}`;
  }
  if (/^\d{2}:\d{2}:\d{2}$/.test(text)) return text.slice(0, 5);
  return text;
}

/** Turns a snake_case key into a label: "total_amount" → "Total amount". */
export function labelFor(key: string): string {
  const text = key.replace(/_/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}
