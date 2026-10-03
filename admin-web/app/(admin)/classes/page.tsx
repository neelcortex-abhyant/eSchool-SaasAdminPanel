"use client";

import ResourceList from "@/components/ResourceList";

type SchoolClass = {
  id: number;
  name: string | null;
  medium_id: number | null;
};

export default function ClassesPage() {
  return (
    <ResourceList<SchoolClass>
      title="Classes"
      endpoint="/classes"
      columns={[
        { key: "id", label: "ID" },
        { key: "name", label: "Name" },
        { key: "medium_id", label: "Medium" },
      ]}
    />
  );
}
