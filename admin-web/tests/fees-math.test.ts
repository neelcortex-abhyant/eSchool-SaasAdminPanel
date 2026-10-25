import { describe, expect, it } from "vitest";
import { allocate, concessionValue, dueLines, splitEvenly, spreadConcession, structureProblems, totals } from "@/lib/ops/fees-math";
import type { FeeStructure } from "@/lib/ops/types";

const structure: FeeStructure = {
  id: 1,
  name: "Class 5",
  session_year_id: 2,
  session_name: "2026-27",
  class_id: 3,
  class_name: "Class 5",
  items: [{ fee_type_id: 1, fee_type_name: "Tuition", category: "tuition", amount: 30000 }],
  installments: [
    { id: 11, name: "Term 1", due_date: "2026-04-15", amount: 10000 },
    { id: 12, name: "Term 2", due_date: "2026-08-15", amount: 10000 },
    { id: 13, name: "Term 3", due_date: "2026-12-15", amount: 10000 },
  ],
  total: 30000,
  late_fee_per_day: 0,
  status: 1,
};

describe("structureProblems", () => {
  const base = { name: "Fees", session_year_id: 2, class_id: 3, items: [{ fee_type_id: 1, amount: 1000 }], installments: [{ name: "One", due_date: "2026-05-01", amount: 1000 }], late_fee_per_day: 0 };

  it("accepts installments that add up to the fees", () => {
    expect(structureProblems(base)).toEqual({});
  });

  it("rejects installments that don't add up", () => {
    expect(structureProblems({ ...base, installments: [{ name: "One", due_date: "2026-05-01", amount: 900 }] }).installments).toMatch(/add up to ₹900.00/);
  });

  it("rejects a fee type used twice and two installments on one day", () => {
    const errors = structureProblems({
      ...base,
      items: [{ fee_type_id: 1, amount: 500 }, { fee_type_id: 1, amount: 500 }],
      installments: [{ name: "A", due_date: "2026-05-01", amount: 500 }, { name: "B", due_date: "2026-05-01", amount: 500 }],
    });
    expect(errors["items.1.fee_type_id"]).toBeTruthy();
    expect(errors["installments.1.due_date"]).toBeTruthy();
  });
});

describe("splitEvenly", () => {
  it("puts leftover paise on the last installment", () => {
    expect(splitEvenly(1000, 3)).toEqual([333.33, 333.33, 333.34]);
    expect(splitEvenly(1000, 3).reduce((a, b) => a + b, 0)).toBeCloseTo(1000, 2);
  });
});

describe("concessions", () => {
  it("values percentages and fixed amounts with caps", () => {
    expect(concessionValue(30000, { kind: "percent", value: 25 })).toBe(7500);
    expect(concessionValue(30000, { kind: "percent", value: 150 })).toBe(30000);
    expect(concessionValue(1000, { kind: "amount", value: 5000 })).toBe(1000);
    expect(concessionValue(1000, null)).toBe(0);
  });

  it("spreads a concession over installments and keeps the total exact", () => {
    const shares = spreadConcession([10000, 10000, 10000], 1000);
    expect(shares).toEqual([333.33, 333.33, 333.34]);
  });
});

describe("dueLines and allocate", () => {
  it("applies concessions and successful payments to installments", () => {
    const lines = dueLines([structure], [{ structure_id: 1, kind: "percent", value: 10 }], [{ structure_id: 1, installment_id: 11, amount: 9000 }], "2026-09-01");
    expect(lines.map((line) => line.balance)).toEqual([0, 9000, 9000]);
    expect(lines[1].overdue).toBe(true);
    expect(lines[2].overdue).toBe(false);
    expect(totals(lines)).toMatchObject({ total: 30000, concession: 3000, paid: 9000, balance: 18000, overdue: 9000 });
  });

  it("allocates a partial payment to the earliest installment first", () => {
    const lines = dueLines([structure], [], [], "2026-05-01");
    expect(allocate(12500, lines)).toEqual([
      { structure_id: 1, installment_id: 11, installment_name: "Term 1", amount: 10000 },
      { structure_id: 1, installment_id: 12, installment_name: "Term 2", amount: 2500 },
    ]);
  });

  it("refuses more than the balance and zero amounts", () => {
    const lines = dueLines([structure], [], [], "2026-05-01");
    expect(() => allocate(30000.01, lines)).toThrow(/owes ₹30000.00/);
    expect(() => allocate(0, lines)).toThrow(/above 0/);
  });
});
