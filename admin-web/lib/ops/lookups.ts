/** Student details stored with sample records, read through the people client (live or sample). */
import { listAll } from "@/lib/academics";
import { peopleService } from "@/lib/people";
import type { StudentRef } from "@/lib/ops/store";

export async function studentRef(studentId: number): Promise<StudentRef & { class_id: number; session_year_id: number }> {
  const student = await peopleService("students").getStudent(studentId);
  return {
    student_id: student.id,
    student_name: student.name,
    admission_no: student.admission_no,
    class_section_id: student.class_section_id,
    class_name: student.class_name,
    section_name: student.section_name,
    class_id: student.class_id,
    session_year_id: student.session_year_id,
  };
}

type StudentDetails = Awaited<ReturnType<typeof studentRef>>;

/** Above this many students one paged list (50 a request) is cheaper than a request each. */
const LIST_THRESHOLD = 25;

/** Details for several students, fetched together; students that can't be loaded are left out. */
export async function studentRefs(ids: number[]): Promise<Map<number, StudentDetails>> {
  const unique = [...new Set(ids.filter((id) => id > 0))];
  const found = new Map<number, StudentDetails>();
  if (unique.length > LIST_THRESHOLD) {
    const wanted = new Set(unique);
    const rows = await listAll((page) => peopleService("students").listStudents({ page, pageSize: 50 })).catch(() => []);
    for (const student of rows) {
      if (!wanted.has(student.id)) continue;
      found.set(student.id, {
        student_id: student.id,
        student_name: student.name,
        admission_no: student.admission_no,
        class_section_id: student.class_section_id,
        class_name: student.class_name,
        section_name: student.section_name,
        class_id: student.class_id,
        session_year_id: student.session_year_id,
      });
    }
  }
  // Anyone the list didn't return (or a short list of ids) is fetched one by one.
  const missing = unique.filter((id) => !found.has(id));
  for (let index = 0; index < missing.length; index += 8) {
    const batch = await Promise.allSettled(missing.slice(index, index + 8).map((id) => studentRef(id)));
    batch.forEach((result) => {
      if (result.status === "fulfilled") found.set(result.value.student_id, result.value);
    });
  }
  return found;
}
