"use client";

import ResourceList from "@/components/ResourceList";

type Attendance = {
  id: number;
  student_id: number | null;
  class_section_id: number | null;
  session_year_id: number | null;
  type: number | null;
  date: string | null;
  remark: string | null;
  school_id: number | null;
};

export default function AttendancesPage() {
  return (
    <ResourceList<Attendance>
      title="Attendances"
      endpoint="/attendances"
      columns={[
        { key: "id", label: "ID" },
        { key: "student_id", label: "Student" },
        { key: "class_section_id", label: "Class section" },
        { key: "date", label: "Date" },
        { key: "type", label: "Type" },
        { key: "school_id", label: "School" },
      ]}
      fields={[
        { key: "student_id", label: "Student ID", type: "number", required: true },
        { key: "class_section_id", label: "Class section ID", type: "number", required: true },
        { key: "session_year_id", label: "Session year ID", type: "number", required: true },
        { key: "date", label: "Date", type: "date", required: true },
        { key: "type", label: "Type (1 present)", type: "number" },
        { key: "remark", label: "Remark" },
        { key: "school_id", label: "School ID", type: "number", required: true, createOnly: true },
      ]}
    />
  );
}
