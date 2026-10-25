/** Student details stored with sample records, read through the people client (live or sample). */
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
