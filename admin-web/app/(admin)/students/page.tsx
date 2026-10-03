"use client";

import ResourceList from "@/components/ResourceList";

type Student = {
  id: number;
  admission_no: string | null;
  roll_number: string | null;
  class_section_id: number | null;
  session_year_id: number | null;
  user_id: number | null;
};

export default function StudentsPage() {
  return (
    <ResourceList<Student>
      title="Students"
      endpoint="/students"
      columns={[
        { key: "id", label: "ID" },
        { key: "admission_no", label: "Admission no" },
        { key: "roll_number", label: "Roll" },
        { key: "class_section_id", label: "Class section" },
        { key: "session_year_id", label: "Session year" },
        { key: "user_id", label: "User" },
      ]}
    />
  );
}
