"use client";

import ResourceList from "@/components/ResourceList";

type Subject = {
  id: number;
  name: string | null;
  code: string | null;
  type: string | null;
  medium_id: number | null;
  school_id: number | null;
};

export default function SubjectsPage() {
  return (
    <ResourceList<Subject>
      title="Subjects"
      endpoint="/subjects"
      columns={[
        { key: "id", label: "ID" },
        { key: "name", label: "Name" },
        { key: "code", label: "Code" },
        { key: "type", label: "Type" },
        { key: "medium_id", label: "Medium" },
        { key: "school_id", label: "School" },
      ]}
      fields={[
        { key: "name", label: "Name", required: true },
        { key: "medium_id", label: "Medium ID", type: "number", required: true },
        { key: "code", label: "Code" },
        { key: "type", label: "Type" },
        { key: "school_id", label: "School ID", type: "number", required: true, createOnly: true },
      ]}
    />
  );
}
