import { describe, expect, it } from "vitest";
import { defaultScale, gradeFor, rangeProblems } from "@/lib/ops/grading-math";
import type { GradeRange } from "@/lib/ops/types";

const range = (grade: string, min: number, max: number, is_pass = true): GradeRange => ({ grade, min_percent: min, max_percent: max, grade_point: null, remark: null, is_pass });
const scale = { ranges: [range("A", 80, 100), range("B", 60, 79.99), range("C", 33, 59.99), range("F", 0, 32.99, false)] };

describe("gradeFor", () => {
  it("finds the band a percentage falls in, bounds included", () => {
    expect(gradeFor(80, scale)?.grade).toBe("A");
    expect(gradeFor(79.99, scale)?.grade).toBe("B");
    expect(gradeFor(33, scale)?.grade).toBe("C");
    expect(gradeFor(0, scale)?.grade).toBe("F");
    expect(gradeFor(100, scale)?.grade).toBe("A");
  });

  it("rounds to two decimals so 79.995 isn't left between bands", () => {
    expect(gradeFor(79.995, scale)?.grade).toBe("A");
    expect(gradeFor(79.994, scale)?.grade).toBe("B");
  });

  it("returns null without a scale or a percentage", () => {
    expect(gradeFor(50, null)).toBeNull();
    expect(gradeFor(null, scale)).toBeNull();
    expect(gradeFor(Number.NaN, scale)).toBeNull();
  });
});

describe("rangeProblems", () => {
  it("accepts ranges that cover 0–100 without overlap", () => {
    expect(rangeProblems(scale.ranges)).toEqual({});
  });

  it("rejects overlapping ranges", () => {
    expect(rangeProblems([range("A", 50, 100), range("B", 0, 50)]).ranges).toMatch(/overlap/);
  });

  it("rejects gaps and ranges that don't reach 0 or 100", () => {
    expect(rangeProblems([range("A", 60, 100), range("B", 0, 50)]).ranges).toMatch(/Nothing covers 50–60/);
    expect(rangeProblems([range("A", 10, 100)]).ranges).toMatch(/0 to 100/);
  });

  it("flags duplicate grades and bad bounds per row", () => {
    const errors = rangeProblems([range("A", 50, 100), range("a", 0, 49.99), range("C", 70, 20)]);
    expect(errors["ranges.1.grade"]).toMatch(/twice/);
    expect(errors["ranges.2.min_percent"]).toMatch(/lower bound/);
  });
});

describe("defaultScale", () => {
  it("prefers the active default, then any active scale", () => {
    expect(defaultScale([{ id: 1, is_default: false, status: 1 as const }, { id: 2, is_default: true, status: 1 as const }])?.id).toBe(2);
    expect(defaultScale([{ id: 1, is_default: true, status: 0 as const }, { id: 2, is_default: false, status: 1 as const }])?.id).toBe(2);
    expect(defaultScale([])).toBeNull();
  });
});
