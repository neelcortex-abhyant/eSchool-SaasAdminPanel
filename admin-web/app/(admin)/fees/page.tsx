"use client";

import ResourceList from "@/components/ResourceList";

type Fee = {
  id: number;
  name: string | null;
  due_date: string | null;
  due_charges: number | null;
  session_year_id: number | null;
  school_id: number | null;
};

export default function FeesPage() {
  return (
    <ResourceList<Fee>
      title="Fees"
      endpoint="/fees"
      columns={[
        { key: "id", label: "ID" },
        { key: "name", label: "Name" },
        { key: "due_date", label: "Due date" },
        { key: "due_charges", label: "Due charges" },
        { key: "session_year_id", label: "Session year" },
        { key: "school_id", label: "School" },
      ]}
      fields={[
        { key: "name", label: "Name", required: true },
        { key: "due_date", label: "Due date", type: "date", required: true },
        { key: "due_charges", label: "Due charges", type: "number" },
        { key: "session_year_id", label: "Session year ID", type: "number", required: true },
        { key: "school_id", label: "School ID", type: "number", required: true, createOnly: true },
      ]}
    />
  );
}
