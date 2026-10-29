/**
 * Grading scales and report cards.
 * Live: /school-admin/grading-scales (GET, POST), /grading-scales/{id} (GET, PATCH, DELETE).
 *   The server calls a grade band's letter `letter` and its bands `bands`.
 *   /school-admin/report-cards (POST {exam_id, grading_scale_id}) stores one card per student
 *   for one exam; GET /report-cards?student_id= lists them. A session report card is put
 *   together here from the offline exam results, using the stored grades where they exist.
 * Sample: scales live in this browser; report cards are built from the offline exam results the
 * exam client returns (live or sample) and graded with the chosen scale.
 */
import { defaultScale, gradeFor, rangeProblems } from "@/lib/ops/grading-math";
import { isOpsLive } from "@/lib/ops/mode";
import { invalid, later, missing, nextId, opsDb, opsSave, conflict } from "@/lib/ops/store";
import type { GradingScale, GradingScaleInput, ReportCard, ReportExam } from "@/lib/ops/types";
import { allPages, num, optNum, optStr, send, str, type Raw } from "@/lib/teaching/client";
import { offlineService } from "@/lib/teaching/offline";
import { peopleService } from "@/lib/people";

export interface GradingService {
  scales(): Promise<GradingScale[]>;
  saveScale(input: GradingScaleInput, id?: number): Promise<GradingScale>;
  removeScale(id: number): Promise<void>;
  reportCard(studentId: number, sessionYearId: number, scaleId?: number): Promise<ReportCard>;
  /** Stores report cards for every student with a processed result in this exam (server only). */
  generate(examId: number, scaleId?: number): Promise<{ created: number; total: number }>;
}

function check(input: GradingScaleInput) {
  const errors: Record<string, string> = { ...rangeProblems(input.ranges) };
  if (!input.name.trim()) errors.name = "Enter a name for the scale.";
  if (Object.keys(errors).length) invalid(errors);
}

function body(input: GradingScaleInput) {
  return {
    name: input.name.trim(),
    description: input.description?.trim() || null,
    is_default: input.is_default,
    status: input.status,
    ranges: input.ranges.map((range) => ({
      grade: range.grade.trim().toUpperCase(),
      min_percent: range.min_percent,
      max_percent: range.max_percent,
      grade_point: range.grade_point,
      remark: range.remark?.trim() || null,
      is_pass: range.is_pass,
    })),
  };
}

const yes = (value: unknown) => value === true || value === 1 || value === "1" || value === "true";

/** A scale as the server returns it (bands with `letter`, 0/1 flags) in this app's shape. */
export function scaleOf(row: Raw): GradingScale {
  const bands = Array.isArray(row.bands) ? (row.bands as Raw[]) : Array.isArray(row.ranges) ? (row.ranges as Raw[]) : [];
  return {
    id: num(row.id),
    name: str(row.name),
    description: optStr(row.description),
    is_default: yes(row.is_default),
    status: num(row.status ?? 1) === 0 ? 0 : 1,
    ranges: bands
      .map((band) => ({
        id: optNum(band.id) ?? undefined,
        grade: str(band.letter ?? band.grade),
        min_percent: num(band.min_percent),
        max_percent: num(band.max_percent),
        grade_point: optNum(band.grade_point),
        remark: optStr(band.remark),
        is_pass: band.is_pass === undefined ? true : yes(band.is_pass),
      }))
      .sort((a, b) => b.min_percent - a.min_percent),
  };
}

function serverBody(input: GradingScaleInput) {
  const { ranges, ...rest } = body(input);
  return { ...rest, bands: ranges.map(({ grade, ...band }, index) => ({ letter: grade, ...band, sort_order: index })) };
}

export const liveGrading: GradingService = {
  async scales() {
    return (await allPages("/school-admin/grading-scales", {}, "Unable to load grading scales.")).map(scaleOf);
  },
  async saveScale(input, id) {
    check(input);
    const row = id
      ? await send("PATCH", `/school-admin/grading-scales/${id}`, serverBody(input), "Unable to save the grading scale.")
      : await send("POST", "/school-admin/grading-scales", serverBody(input), "Unable to add the grading scale.");
    return scaleOf(row);
  },
  async removeScale(id) {
    await send("DELETE", `/school-admin/grading-scales/${id}`, undefined, "Unable to delete the grading scale.");
  },
  async reportCard(studentId, sessionYearId, scaleId) {
    const scales = await liveGrading.scales();
    const scale = (scaleId ? scales.find((item) => item.id === scaleId) : null) ?? defaultScale(scales);
    const card = await buildReportCard(studentId, sessionYearId, scale ?? null);
    // The server's stored cards give each exam a PDF; with the default scale their grades are shown too.
    const stored = await allPages("/school-admin/report-cards", { student_id: studentId }, "Unable to load the report card.").catch(() => [] as Raw[]);
    const byExam = new Map(stored.map((row) => [num(row.exam_id), row]));
    return {
      ...card,
      exams: card.exams.map((exam) => {
        const row = byExam.get(exam.exam_id);
        if (!row) return exam;
        return { ...exam, grade: scaleId ? exam.grade : optStr(row.letter_grade) ?? exam.grade, report_id: num(row.id) || null };
      }),
    };
  },
  async generate(examId, scaleId) {
    const data = await send("POST", "/school-admin/report-cards", { exam_id: examId, grading_scale_id: scaleId ?? null }, "Unable to generate report cards.");
    return { created: num(data.created), total: num(data.total) };
  },
};

/** Builds a report card from processed offline exam results (the same data the results pages show). */
async function buildReportCard(studentId: number, sessionYearId: number, scale: GradingScale | null): Promise<ReportCard> {
  const student = await peopleService("students").getStudent(studentId);
  const exams = (await offlineService().list({ sessionYearId, classSectionId: student.class_section_id, pageSize: 50 })).items;
  const reports: ReportExam[] = [];
  for (const exam of exams.sort((a, b) => (a.exam_date ?? "").localeCompare(b.exam_date ?? ""))) {
    const result = (await offlineService().results(exam.id)).find((row) => row.student_id === studentId);
    if (!result) continue;
    reports.push({
      exam_id: exam.id,
      exam_name: exam.name,
      exam_date: exam.exam_date,
      published: exam.publish,
      subjects: result.subjects.map((subject) => {
        const percent = subject.included && subject.max_marks ? ((subject.marks_obtained ?? 0) / subject.max_marks) * 100 : null;
        return {
          subject_name: subject.subject_name ?? "Subject",
          marks_obtained: subject.marks_obtained,
          max_marks: subject.max_marks,
          status: subject.status,
          grade: subject.included ? gradeFor(percent, scale)?.grade ?? null : null,
          passed: subject.passed,
        };
      }),
      total_obtained: result.total_obtained,
      total_max: result.total_max_marks,
      percentage: result.percentage,
      grade: gradeFor(result.percentage, scale)?.grade ?? null,
      passed: result.passed,
    });
  }
  const totalObtained = reports.reduce((sum, exam) => sum + exam.total_obtained, 0);
  const totalMax = reports.reduce((sum, exam) => sum + exam.total_max, 0);
  const percentage = totalMax ? Math.round((totalObtained / totalMax) * 10000) / 100 : 0;
  const passed = reports.length ? reports.every((exam) => exam.passed) : null;
  const primary = student.guardians.find((guardian) => guardian.is_primary) ?? student.guardians[0];
  return {
    student_id: student.id,
    student_name: student.name,
    admission_no: student.admission_no,
    roll_number: student.roll_number,
    class_name: student.class_name,
    section_name: student.section_name,
    session_year_id: sessionYearId,
    session_name: student.session_name,
    guardian_name: primary?.name ?? student.guardian_name,
    exams: reports,
    overall: { total_obtained: totalObtained, total_max: totalMax, percentage, grade: reports.length ? gradeFor(percentage, scale)?.grade ?? null : null, passed },
    // Promotion follows the school's rule on the server; here it's shown only once every exam is processed.
    promotion: reports.length && reports.length === exams.length ? (passed ? "Promoted" : "Not promoted") : null,
    scale_name: scale?.name ?? null,
  };
}

export const mockGrading: GradingService = {
  async scales() {
    return later(opsDb().scales);
  },
  async saveScale(input, id) {
    check(input);
    const db = opsDb();
    if (db.scales.some((scale) => scale.id !== id && scale.name.trim().toLowerCase() === input.name.trim().toLowerCase())) conflict("A grading scale with this name already exists.", "name");
    let rangeId = Math.max(0, ...db.scales.flatMap((scale) => scale.ranges.map((range) => range.id ?? 0)));
    const row: GradingScale = { id: id ?? nextId(db.scales), ...body(input), ranges: body(input).ranges.map((range) => ({ ...range, id: (rangeId += 1) })) };
    if (row.is_default) db.scales.forEach((scale) => (scale.is_default = false));
    const index = db.scales.findIndex((scale) => scale.id === id);
    if (id && index < 0) missing("Grading scale");
    if (index >= 0) db.scales[index] = row;
    else db.scales.push(row);
    if (!db.scales.some((scale) => scale.is_default)) db.scales[0].is_default = true;
    opsSave();
    return later(row);
  },
  async removeScale(id) {
    const db = opsDb();
    const scale = db.scales.find((item) => item.id === id) ?? missing("Grading scale");
    if (scale.is_default) conflict("Choose another default scale before deleting this one.");
    db.scales = db.scales.filter((item) => item.id !== id);
    opsSave();
    await later(null);
  },
  async reportCard(studentId, sessionYearId, scaleId) {
    const scales = opsDb().scales;
    const scale = (scaleId ? scales.find((item) => item.id === scaleId) : null) ?? defaultScale(scales);
    return buildReportCard(studentId, sessionYearId, scale ?? null);
  },
  async generate() {
    return later({ created: 0, total: 0 });
  },
};

export function gradingService(): GradingService {
  return isOpsLive("grading") ? liveGrading : mockGrading;
}

/** The grading scale to apply to results: the default from the grading service, or null if none. */
export async function activeScale(): Promise<GradingScale | null> {
  try {
    return defaultScale(await gradingService().scales());
  } catch {
    return null;
  }
}
