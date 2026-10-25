/** Grade ranges: checks and lookup, shared by the grading pages, results and report cards. */
import type { GradeRange, GradingScale } from "@/lib/ops/types";

/** Problems with a scale's ranges, by field ("ranges" for the list as a whole, "ranges.N.field" per row). */
export function rangeProblems(ranges: GradeRange[]): Record<string, string> {
  const errors: Record<string, string> = {};
  if (ranges.length === 0) errors.ranges = "Add at least one grade range.";
  const seen = new Set<string>();
  ranges.forEach((range, index) => {
    const grade = range.grade.trim().toUpperCase();
    if (!grade) errors[`ranges.${index}.grade`] = "Enter the grade.";
    else if (seen.has(grade)) errors[`ranges.${index}.grade`] = `${range.grade} is used twice.`;
    seen.add(grade);
    if (!Number.isFinite(range.min_percent) || !Number.isFinite(range.max_percent) || range.min_percent < 0 || range.max_percent > 100) {
      errors[`ranges.${index}.min_percent`] = "Percentages must be between 0 and 100.";
    } else if (range.min_percent > range.max_percent) {
      errors[`ranges.${index}.min_percent`] = "The lower bound can't be above the upper bound.";
    }
  });
  if (Object.keys(errors).length) return errors;
  const sorted = [...ranges].sort((a, b) => a.min_percent - b.min_percent);
  for (let i = 1; i < sorted.length; i += 1) {
    if (sorted[i].min_percent <= sorted[i - 1].max_percent) {
      errors.ranges = `${sorted[i - 1].grade} (${sorted[i - 1].min_percent}–${sorted[i - 1].max_percent}) and ${sorted[i].grade} (${sorted[i].min_percent}–${sorted[i].max_percent}) overlap.`;
      return errors;
    }
  }
  if (sorted[0].min_percent > 0 || sorted[sorted.length - 1].max_percent < 100) {
    errors.ranges = "The ranges must cover every percentage from 0 to 100.";
    return errors;
  }
  for (let i = 1; i < sorted.length; i += 1) {
    // Ranges are inclusive and percentages have up to two decimals, so a gap bigger than 0.01 leaves marks ungraded.
    if (sorted[i].min_percent - sorted[i - 1].max_percent > 0.01 + 1e-9) {
      errors.ranges = `Nothing covers ${sorted[i - 1].max_percent}–${sorted[i].min_percent}%.`;
      return errors;
    }
  }
  return errors;
}

/** The range a percentage falls in. Percentages between two ranges' bounds (e.g. 89.995) round to 2 decimals first. */
export function gradeFor(percent: number | null | undefined, scale: Pick<GradingScale, "ranges"> | null | undefined): GradeRange | null {
  if (percent === null || percent === undefined || !Number.isFinite(percent) || !scale) return null;
  const value = Math.round(percent * 100) / 100;
  return scale.ranges.find((range) => value >= range.min_percent && value <= range.max_percent) ?? null;
}

export function defaultScale<T extends Pick<GradingScale, "is_default" | "status">>(scales: T[]): T | null {
  return scales.find((scale) => scale.is_default && scale.status === 1) ?? scales.find((scale) => scale.status === 1) ?? null;
}
