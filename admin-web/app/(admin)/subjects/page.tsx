"use client";

import ResourceList from "@/components/ResourceList";

type Subject = {
  id: number;
  name: string | null;
  code: string | null;
  type: string | null;
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
      ]}
    />
  );
}
