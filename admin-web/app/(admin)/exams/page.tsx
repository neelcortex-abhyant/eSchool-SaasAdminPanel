"use client";

import ResourceList from "@/components/ResourceList";

type Exam = {
  id: number;
  name: string | null;
  description: string | null;
  class_id: number | null;
  session_year_id: number | null;
  publish: number | null;
  school_id: number | null;
};

export default function ExamsPage() {
  return (
    <ResourceList<Exam>
      title="Exams"
      endpoint="/exams"
      columns={[
        { key: "id", label: "ID" },
        { key: "name", label: "Name" },
        { key: "class_id", label: "Class" },
        { key: "session_year_id", label: "Session year" },
        { key: "publish", label: "Published" },
        { key: "school_id", label: "School" },
      ]}
      fields={[
        { key: "name", label: "Name", required: true },
        { key: "class_id", label: "Class ID", type: "number", required: true },
        { key: "session_year_id", label: "Session year ID", type: "number", required: true },
        { key: "description", label: "Description", type: "textarea" },
        { key: "publish", label: "Publish (0 or 1)", type: "number" },
        { key: "school_id", label: "School ID", type: "number", required: true, createOnly: true },
      ]}
    />
  );
}
