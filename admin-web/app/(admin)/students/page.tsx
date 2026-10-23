"use client";

import ResourceList from "@/components/ResourceList";

type Student = {
  id: number;
  admission_no: string | null;
  roll_number: number | null;
  class_section_id: number | null;
  session_year_id: number | null;
  user_id: number | null;
  guardian_id: number | null;
  admission_date: string | null;
  school_id: number | null;
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
        { key: "school_id", label: "School" },
      ]}
      fields={[
        { key: "first_name", label: "First name", required: true, createOnly: true },
        { key: "last_name", label: "Last name", required: true, createOnly: true },
        { key: "email", label: "Email", required: true, createOnly: true },
        { key: "admission_no", label: "Admission no", required: true },
        { key: "admission_date", label: "Admission date", type: "date", required: true },
        { key: "class_section_id", label: "Class section ID", type: "number", required: true },
        { key: "session_year_id", label: "Session year ID", type: "number", required: true },
        { key: "guardian_id", label: "Guardian user ID", type: "number", required: true },
        { key: "school_id", label: "School ID", type: "number", required: true, createOnly: true },
        { key: "roll_number", label: "Roll number", type: "number" },
      ]}
    />
  );
}
