"use client";

import ResourceList from "@/components/ResourceList";

type Attendance = {
  id: number;
  student_id: number | null;
  type: string | null;
  date: string | null;
  remark: string | null;
};

export default function AttendancesPage() {
  return (
    <ResourceList<Attendance>
      title="Attendances"
      endpoint="/attendances"
      columns={[
        { key: "id", label: "ID" },
        { key: "student_id", label: "Student" },
        { key: "type", label: "Type" },
        { key: "date", label: "Date" },
        { key: "remark", label: "Remark" },
      ]}
    />
  );
}
