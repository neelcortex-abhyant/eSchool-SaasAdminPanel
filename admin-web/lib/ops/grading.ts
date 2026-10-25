/**
 * Grading scales and report cards.
 * Live (proposed, see backend/docs/FEES_TRANSPORT_GRADING_API_CONTRACT.md):
 *   /school-admin/grading-scales (GET, POST), /grading-scales/{id} (GET, PATCH, DELETE)
 *   /school-admin/report-cards/{student_id}?session_year_id= (GET), /report-cards/{student_id}/pdf
 * Sample: scales live in this browser; report cards are built from the offline exam results the
 * exam client returns (live or sample) and graded with the chosen scale.
 */
import { defaultScale, gradeFor, rangeProblems } from "@/lib/ops/grading-math";
import { isOpsLive } from "@/lib/ops/mode";
import { invalid, later, missing, nextId, opsDb, opsSave, conflict } from "@/lib/ops/store";
import type { GradingScale, GradingScaleInput, ReportCard, ReportExam } from "@/lib/ops/types";
import { get, send } from "@/lib/teaching/client";
import { offlineService } from "@/lib/teaching/offline";
import { peopleService } from "@/lib/people";

export interface GradingService {
  scales(): Promise<GradingScale[]>;
  saveScale(input: GradingScaleInput, id?: number): Promise<GradingScale>;
  removeScale(id: number): Promise<void>;
  reportCard(studentId: number, sessionYearId: number, scaleId?: number): Promise<ReportCard>;
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

export const liveGrading: GradingService = {
  async scales() {
    const data = await get<{ items?: GradingScale[] }>("/school-admin/grading-scales", {}, "Unable to load grading scales.");
    return data.items ?? [];
  },
  async saveScale(input, id) {
    check(input);
    return id
      ? send<GradingScale>("PATCH", `/school-admin/grading-scales/${id}`, body(input), "Unable to save the grading scale.")
      : send<GradingScale>("POST", "/school-admin/grading-scales", body(input), "Unable to add the grading scale.");
  },
  async removeScale(id) {
    await send("DELETE", `/school-admin/grading-scales/${id}`, undefined, "Unable to delete the grading scale.");
  },
  async reportCard(studentId, sessionYearId, scaleId) {
    return get<ReportCard>(`/school-admin/report-cards/${studentId}`, { session_year_id: sessionYearId, grading_scale_id: scaleId }, "Unable to load the report card.");
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
