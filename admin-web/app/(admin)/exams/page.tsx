"use client";

import ResourceList from "@/components/ResourceList";

type Exam = {
  id: number;
  name: string | null;
  class_id: number | null;
  publish: number | boolean | null;
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
        { key: "publish", label: "Publish" },
      ]}
    />
  );
}
