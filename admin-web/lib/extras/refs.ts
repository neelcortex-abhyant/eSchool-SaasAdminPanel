/**
 * Names for the ids the 0039 routes return (sessions, classes, sections, subjects, teachers,
 * staff, students and the module's own categories), so tables show names instead of numbers.
 */
import { academicsService, listAll } from "@/lib/academics";
import { studentRefs } from "@/lib/ops/lookups";
import { listRows, staffDirectory } from "@/lib/extras/api";
import { num, str } from "@/lib/teaching/client";

/** A built-in kind of id, or another list on the server whose rows have `label`. */
export type RefKind = "session" | "class" | "section" | "subject" | "teacher" | "staff" | "staff-user" | "student" | { path: string; label: string };

export type RefOption = { value: string; label: string };

export function refKey(kind: RefKind): string {
  return typeof kind === "string" ? kind : `${kind.path}#${kind.label}`;
}

/** Every choice for a kind (students are searched instead, so they have none here). */
export async function refOptions(kind: RefKind): Promise<RefOption[]> {
  if (typeof kind !== "string") {
    return (await listRows(kind.path)).map((row) => ({ value: String(num(row.id)), label: str(row[kind.label]) || `#${num(row.id)}` }));
  }
  switch (kind) {
    case "session":
      return (await listAll((page) => academicsService("sessions").listSessions({ page, pageSize: 50 }))).map((row) => ({ value: String(row.id), label: `${row.name}${row.is_active ? " (current)" : ""}` }));
    case "class":
      return (await listAll((page) => academicsService("classes").listClasses({ page, pageSize: 50 }))).map((row) => ({ value: String(row.id), label: row.name }));
    case "section":
      return (await listAll((page) => academicsService("sections").listSections({ page, pageSize: 50 })))
        .map((row) => ({ value: String(row.id), label: `${row.class_name} ${row.section_name}` }))
        .sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }));
    case "subject":
      return (await listAll((page) => academicsService("subjects").listSubjects({ page, pageSize: 50 }))).map((row) => ({ value: String(row.id), label: row.name }));
    case "teacher":
      return (await academicsService("assignments").listTeachers()).map((row) => ({ value: String(row.id), label: row.name }));
    case "staff":
      return (await staffDirectory()).map((row) => ({ value: String(row.staff_id), label: `${row.name}${row.designation ? ` · ${row.designation}` : ""}` }));
    case "staff-user":
      return (await staffDirectory()).filter((row) => row.user_id).map((row) => ({ value: String(row.user_id), label: `${row.name}${row.designation ? ` · ${row.designation}` : ""}` }));
    case "student":
      return [];
  }
}

/** id → name for the ids a table shows. Students are looked up one by one, so only `ids` are loaded. */
export async function refNames(kind: RefKind, ids: number[]): Promise<Map<number, string>> {
  if (kind === "student") {
    const found = await studentRefs(ids);
    return new Map([...found].map(([id, row]) => [id, `${row.student_name}${row.admission_no ? ` (${row.admission_no})` : ""}`]));
  }
  const options = await refOptions(kind).catch(() => [] as RefOption[]);
  return new Map(options.map((option) => [Number(option.value), option.label]));
}
