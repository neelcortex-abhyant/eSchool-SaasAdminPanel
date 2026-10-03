"use client";

import ResourceList from "@/components/ResourceList";

type Fee = {
  id: number;
  name: string | null;
  due_date: string | null;
  due_charges: number | null;
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
      ]}
    />
  );
}
