import { describe, expect, it } from "vitest";
import { parseMarksCsv } from "@/lib/teaching/marksCsv";

const roster = [
  { id: 1, name: "Aarav", admission_no: "ADM1" },
  { id: 2, name: "Diya", admission_no: "ADM2" },
  { id: 3, name: "Kabir", admission_no: "ADM3" },
];

describe("parseMarksCsv", () => {
  it("reads marks, absences and withheld rows", () => {
    const { rows, problem } = parseMarksCsv("admission_no,marks,status\nADM1,72,present\nadm2,AB,\nADM3,,withheld\n", roster, 80);
    expect(problem).toBe("");
    expect(rows.map((row) => [row.student_id, row.status, row.marks_obtained, row.error])).toEqual([
      [1, "present", 72, ""],
      [2, "absent", null, ""],
      [3, "withheld", null, ""],
    ]);
  });

  it("flags unknown students, duplicates, missing and out-of-range marks", () => {
    const { rows } = parseMarksCsv("Admission No,Marks\nADM9,10\nADM1,90\nADM1,10\nADM2,\n", roster, 80);
    expect(rows[0].error).toMatch(/isn't a student/);
    expect(rows[1].error).toMatch(/between 0 and 80/);
    expect(rows[2].error).toMatch(/more than once/);
    expect(rows[3].error).toMatch(/Enter the marks/);
    expect(rows.every((row) => row.line > 1)).toBe(true);
  });

  it("needs the column names in the first row", () => {
    expect(parseMarksCsv("foo,bar\n1,2", roster, 80).problem).toMatch(/first row/);
    expect(parseMarksCsv("", roster, 80).problem).toMatch(/empty/);
  });

  it("handles quoted cells and a byte-order mark", () => {
    const { rows } = parseMarksCsv('﻿admission_no,marks\n"ADM1","45.5"', roster, 80);
    expect(rows[0]).toMatchObject({ student_id: 1, marks_obtained: 45.5, error: "" });
  });
});
