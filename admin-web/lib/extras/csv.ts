/** CSV for the bulk imports: parsing (quoted values, commas and line breaks inside quotes) and the rows the server takes. */

export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  const source = text.replace(/^﻿/, "");
  for (let i = 0; i < source.length; i += 1) {
    const char = source[i];
    if (quoted) {
      if (char === '"' && source[i + 1] === '"') {
        cell += '"';
        i += 1;
      } else if (char === '"') quoted = false;
      else cell += char;
    } else if (char === '"') quoted = true;
    else if (char === ",") {
      row.push(cell);
      cell = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && source[i + 1] === "\n") i += 1;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else cell += char;
  }
  if (cell || row.length) {
    row.push(cell);
    rows.push(row);
  }
  return rows.filter((cells) => cells.some((value) => value.trim()));
}

export type ImportColumn = { key: string; required: boolean; number?: boolean; hint: string };

export type ImportResult = { rows: Record<string, string | number>[]; problems: string[] };

/** Rows keyed by the header line; header names are matched case-insensitively. */
export function csvRows(text: string, columns: ImportColumn[], limit = 500): ImportResult {
  const table = parseCsv(text);
  if (table.length < 2) return { rows: [], problems: ["The file needs a header line and at least one row."] };
  const header = table[0].map((name) => name.trim().toLowerCase());
  const missing = columns.filter((column) => column.required && !header.includes(column.key));
  if (missing.length) return { rows: [], problems: [`Missing columns: ${missing.map((column) => column.key).join(", ")}.`] };
  if (table.length - 1 > limit) return { rows: [], problems: [`At most ${limit} rows at a time; this file has ${table.length - 1}.`] };
  const problems: string[] = [];
  const rows = table.slice(1).map((cells, index) => {
    const row: Record<string, string | number> = {};
    for (const column of columns) {
      const at = header.indexOf(column.key);
      const value = at >= 0 ? (cells[at] ?? "").trim() : "";
      if (!value) {
        if (column.required) problems.push(`Row ${index + 2}: ${column.key} is empty.`);
        continue;
      }
      if (column.number) {
        if (Number.isNaN(Number(value))) problems.push(`Row ${index + 2}: ${column.key} must be a number.`);
        else row[column.key] = Number(value);
      } else row[column.key] = value;
    }
    return row;
  });
  return { rows, problems };
}

/** The server's 422 for a failed import: {"errors": [{"row": 0, "detail": "..."}]} inside `detail`. */
export function importErrors(detail: unknown): string[] {
  try {
    const parsed = typeof detail === "string" ? JSON.parse(detail) : detail;
    const errors = (parsed as { errors?: { row: number; detail: string }[] })?.errors;
    if (Array.isArray(errors)) return errors.map((item) => `Row ${Number(item.row) + 2}: ${item.detail}`);
  } catch {
    // Not the row list; the caller shows the message as it is.
  }
  return [];
}

export const STUDENT_IMPORT_COLUMNS: ImportColumn[] = [
  { key: "first_name", required: true, hint: "Diya" },
  { key: "last_name", required: true, hint: "Patel" },
  { key: "email", required: true, hint: "diya@example.com" },
  { key: "admission_no", required: true, hint: "ADM2026001" },
  { key: "admission_date", required: true, hint: "2026-04-01" },
  { key: "session_year_id", required: true, number: true, hint: "Session id" },
  { key: "class_section_id", required: true, number: true, hint: "Section id" },
  { key: "guardian_id", required: true, number: true, hint: "Parent's user id" },
  { key: "roll_number", required: false, number: true, hint: "12" },
  { key: "password", required: false, hint: "Leave empty for a random one" },
];

export const STAFF_IMPORT_COLUMNS: ImportColumn[] = [
  { key: "first_name", required: true, hint: "Ravi" },
  { key: "last_name", required: true, hint: "Kumar" },
  { key: "email", required: true, hint: "ravi@example.com" },
  { key: "password", required: true, hint: "At least 8 characters" },
  { key: "mobile", required: false, hint: "9876543210" },
  { key: "designation", required: false, hint: "Accountant" },
  { key: "department", required: false, hint: "Office" },
  { key: "joining_date", required: false, hint: "2026-04-01" },
  { key: "salary", required: false, number: true, hint: "25000" },
  { key: "employee_id", required: false, hint: "Leave empty to number automatically" },
];

export const TEACHER_IMPORT_COLUMNS: ImportColumn[] = [
  { key: "first_name", required: true, hint: "Neha" },
  { key: "last_name", required: true, hint: "Sharma" },
  { key: "email", required: true, hint: "neha@example.com" },
  { key: "password", required: true, hint: "At least 8 characters" },
  { key: "mobile", required: false, hint: "9876543210" },
  { key: "gender", required: false, hint: "female" },
  { key: "qualification", required: false, hint: "M.Sc., B.Ed." },
  { key: "designation", required: false, hint: "PGT Physics" },
  { key: "department", required: false, hint: "Science" },
  { key: "joining_date", required: false, hint: "2026-04-01" },
  { key: "salary", required: false, number: true, hint: "45000" },
  { key: "employee_id", required: false, hint: "Leave empty to number automatically" },
];

/** Problems the server would refuse a teacher row for, checked before anything is sent. */
export function teacherRowProblems(rows: Record<string, string | number>[]): string[] {
  const seen = new Set<string>();
  const problems: string[] = [];
  rows.forEach((row, index) => {
    const line = index + 2;
    const email = String(row.email ?? "").trim().toLowerCase();
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) problems.push(`Row ${line}: email isn't valid.`);
    if (email && seen.has(email)) problems.push(`Row ${line}: ${email} appears twice in the file.`);
    seen.add(email);
    if (String(row.password ?? "").length > 0 && String(row.password).length < 8) problems.push(`Row ${line}: password must be at least 8 characters.`);
    if (typeof row.salary === "number" && row.salary < 0) problems.push(`Row ${line}: salary can't be negative.`);
    if (row.joining_date && !/^\d{4}-\d{2}-\d{2}$/.test(String(row.joining_date))) problems.push(`Row ${line}: joining_date must be YYYY-MM-DD.`);
  });
  return problems;
}

export function csvTemplate(columns: ImportColumn[]): string {
  return `${columns.map((column) => column.key).join(",")}\n`;
}
