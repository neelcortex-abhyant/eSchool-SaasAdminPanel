"use client";

import ResourceList from "@/components/ResourceList";

type SchoolClass = {
  id: number;
  name: string | null;
  medium_id: number | null;
  include_semesters: number | null;
  school_id: number | null;
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
        { key: "school_id", label: "School" },
      ]}
      fields={[
        { key: "name", label: "Name", required: true },
        { key: "medium_id", label: "Medium ID", type: "number", required: true },
        { key: "school_id", label: "School ID", type: "number", required: true, createOnly: true },
        { key: "include_semesters", label: "Include semesters (0 or 1)", type: "number" },
      ]}
    />
  );
}
