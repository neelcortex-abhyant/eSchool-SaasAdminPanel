"use client";

import ResourceList from "@/components/ResourceList";

type School = {
  id: number;
  name: string | null;
  code: string | null;
  status: string | number | null;
  database_name: string | null;
};

export default function SchoolsPage() {
  return (
    <ResourceList<School>
      title="Schools"
      endpoint="/schools"
      columns={[
        { key: "id", label: "ID" },
        { key: "name", label: "Name" },
        { key: "code", label: "Code" },
        { key: "status", label: "Status" },
        { key: "database_name", label: "Database" },
      ]}
    />
  );
}
