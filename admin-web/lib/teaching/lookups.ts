/**
 * Names for ids picked in the forms, read through the academics client (live or sample, as
 * configured). The sample-data teaching clients store these names on the records they create.
 */
import { academicsService, listAll } from "@/lib/academics";
import type { Placement } from "@/lib/teaching/types";

export async function placementOf(sessionYearId: number, classSectionId: number): Promise<Placement> {
  const sections = await listAll((page) => academicsService("sections").listSections({ page, pageSize: 50 }));
  const row = sections.find((item) => item.id === classSectionId);
  return {
    session_year_id: sessionYearId,
    class_section_id: classSectionId,
    class_id: row?.class_id ?? 0,
    class_name: row?.class_name ?? `Class section #${classSectionId}`,
    section_name: row?.section_name ?? "",
  };
}

/** Class and section names by class section id, for live rows that carry only ids. */
export async function sectionMap(): Promise<Map<number, Placement>> {
  const sections = await listAll((page) => academicsService("sections").listSections({ page, pageSize: 50 }));
  return new Map(
    sections.map((row) => [row.id, { session_year_id: 0, class_section_id: row.id, class_id: row.class_id, class_name: row.class_name, section_name: row.section_name }]),
  );
}

export async function subjectName(subjectId: number): Promise<string> {
  const subjects = await listAll((page) => academicsService("subjects").listSubjects({ page, pageSize: 50 }));
  return subjects.find((item) => item.id === subjectId)?.name ?? `Subject #${subjectId}`;
}

export async function teacherName(teacherId: number): Promise<string> {
  const teachers = await academicsService("assignments").listTeachers();
  return teachers.find((item) => item.id === teacherId)?.name ?? `Teacher #${teacherId}`;
}
