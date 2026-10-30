import { describe, expect, it } from "vitest";
import { numberByName, rollProblems, withRoll } from "@/components/extras/StudentBulk";
import type { Student } from "@/lib/people";

describe("assign roll numbers", () => {
  it("rejects repeats and anything but whole numbers from 1", () => {
    expect(rollProblems({ 1: "3", 2: "3", 3: "", 4: "0", 5: "2.5", 6: "7" })).toEqual({
      1: "Roll 3 is used twice.",
      2: "Roll 3 is used twice.",
      4: "Use a whole number from 1.",
      5: "Use a whole number from 1.",
    });
    expect(rollProblems({ 1: "1", 2: "2" })).toEqual({});
  });

  it("numbers students in order of name", () => {
    expect(numberByName([{ id: 9, name: "Zara" }, { id: 4, name: "Arjun" }, { id: 6, name: "Meera" }])).toEqual({ 4: "1", 6: "2", 9: "3" });
  });

  it("keeps every saved detail and changes only the roll number", () => {
    const student = {
      id: 7, first_name: "Asha", last_name: "Rao", name: "Asha Rao", dob: "2015-04-02", gender: "female", admission_no: "ADM7", admission_date: "2024-06-01",
      session_year_id: 3, class_section_id: 11, roll_number: 4, email: null, mobile: "98765", current_address: "MG Road", permanent_address: null, status: 1,
    } as unknown as Student;
    expect(withRoll(student, 12)).toEqual({
      first_name: "Asha", last_name: "Rao", dob: "2015-04-02", gender: "female", admission_no: "ADM7", admission_date: "2024-06-01",
      session_year_id: 3, class_section_id: 11, roll_number: 12, email: null, mobile: "98765", current_address: "MG Road", permanent_address: null, status: 1,
    });
  });
});
