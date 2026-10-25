/**
 * Reads a marks CSV for one exam paper. Header: admission_no, marks, status (status optional:
 * present, absent or withheld; "AB" also means absent). Every row is checked against the
 * paper's roster and maximum marks before anything is sent.
 */
import type { MarkStatus } from "@/lib/teaching/offlineTypes";

export type CsvRosterStudent = { id: number; name: string; admission_no: string };

export type CsvMarkRow = {
  line: number;
  admission_no: string;
  student_id: number | null;
  student_name: string | null;
  status: MarkStatus;
  marks_obtained: number | null;
  error: string;
};

export const MARKS_CSV_TEMPLATE_HEADER = "admission_no,marks,status";

function cells(line: string): string[] {
  const out: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') {
        cell += '"';
        i += 1;
      } else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") {
      out.push(cell.trim());
      cell = "";
    } else cell += ch;
  }
  out.push(cell.trim());
  return out;
}

export function parseMarksCsv(text: string, roster: CsvRosterStudent[], maxMarks: number): { rows: CsvMarkRow[]; problem: string } {
  const lines = text.replace(/^﻿/, "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length === 0) return { rows: [], problem: "The file is empty." };
  const header = cells(lines[0]).map((cell) => cell.toLowerCase().replace(/\s+/g, "_"));
  const admissionCol = header.findIndex((cell) => cell === "admission_no" || cell === "admission_number");
  const marksCol = header.findIndex((cell) => cell === "marks" || cell === "marks_obtained");
  const statusCol = header.indexOf("status");
  if (admissionCol < 0 || marksCol < 0) return { rows: [], problem: "The first row must name the columns: admission_no, marks and (optionally) status." };
  const byAdmission = new Map(roster.map((student) => [student.admission_no.trim().toUpperCase(), student]));
  const seen = new Set<string>();
  const rows = lines.slice(1).map((line, index): CsvMarkRow => {
    const values = cells(line);
    const admission = (values[admissionCol] ?? "").trim();
    const rawMarks = (values[marksCol] ?? "").trim();
    const rawStatus = (statusCol >= 0 ? values[statusCol] ?? "" : "").trim().toLowerCase();
    const student = byAdmission.get(admission.toUpperCase()) ?? null;
    let status: MarkStatus = "present";
    if (rawStatus === "absent" || rawStatus === "ab" || rawMarks.toUpperCase() === "AB") status = "absent";
    else if (rawStatus === "withheld") status = "withheld";
    const marks = status === "present" && rawMarks !== "" ? Number(rawMarks) : null;
    let error = "";
    if (!admission) error = "Admission number is missing.";
    else if (!student) error = `${admission} isn't a student of this class and session.`;
    else if (seen.has(admission.toUpperCase())) error = `${admission} appears more than once.`;
    else if (rawStatus && !["present", "absent", "ab", "withheld"].includes(rawStatus)) error = "Status must be present, absent or withheld.";
    else if (status === "present" && (marks === null || Number.isNaN(marks))) error = "Enter the marks, or set the status to absent.";
    else if (status === "present" && marks !== null && (marks < 0 || marks > maxMarks)) error = `Marks must be between 0 and ${maxMarks}.`;
    if (admission) seen.add(admission.toUpperCase());
    return { line: index + 2, admission_no: admission, student_id: student?.id ?? null, student_name: student?.name ?? null, status, marks_obtained: marks, error };
  });
  return { rows, problem: rows.length ? "" : "The file has a header but no rows." };
}
