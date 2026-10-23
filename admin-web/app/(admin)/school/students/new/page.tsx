"use client";

import { useRouter } from "next/navigation";
import { uploadFiles } from "@/components/people/Files";
import { PeoplePage, flashMessage } from "@/components/people/PeoplePage";
import { StudentForm } from "@/components/people/StudentForm";
import { peopleService, type StudentCreateInput } from "@/lib/people";
import { IconUsers } from "@/lib/icons";

const service = peopleService("students");

export default function AdmitStudentPage() {
  const router = useRouter();
  return (
    <PeoplePage
      module="students"
      title="Admit student"
      description="Fill in each section. Fields marked * are required."
      icon={<IconUsers width={18} height={18} />}
      back={{ href: "/school/students", label: "Students" }}
    >
      <StudentForm
        student={null}
        cancelHref="/school/students"
        onSave={async ({ input, photo, documents }) => {
          const student = await service.createStudent(input as StudentCreateInput);
          const failures = await uploadFiles(service, "students", student.id, photo, documents);
          if (failures.length) {
            flashMessage(`${student.name} was admitted (${student.admission_no}), but some files didn't upload. ${failures.join(" ")} Upload them again from Edit.`, "error");
          } else {
            flashMessage(`${student.name} was admitted with admission number ${student.admission_no}.`);
          }
          router.push(`/school/students/${student.id}`);
        }}
      />
    </PeoplePage>
  );
}
