"use client";

import ResourceList from "@/components/ResourceList";

type Leave = {
  id: number;
  user_id: number | null;
  reason: string | null;
  status: number | null;
  from_date: string | null;
  to_date: string | null;
  session_year_id: number | null;
  school_id: number | null;
};

export default function LeavesPage() {
  return (
    <ResourceList<Leave>
      title="Leaves"
      endpoint="/leaves"
      columns={[
        { key: "id", label: "ID" },
        { key: "user_id", label: "User" },
        { key: "reason", label: "Reason" },
        { key: "from_date", label: "From" },
        { key: "to_date", label: "To" },
        { key: "status", label: "Status" },
        { key: "school_id", label: "School" },
      ]}
      fields={[
        { key: "user_id", label: "User ID", type: "number", required: true },
        { key: "reason", label: "Reason", required: true },
        { key: "from_date", label: "From", type: "date", required: true },
        { key: "to_date", label: "To", type: "date", required: true },
        { key: "session_year_id", label: "Session year ID", type: "number", required: true },
        { key: "status", label: "Status", type: "number" },
        { key: "school_id", label: "School ID", type: "number", required: true, createOnly: true },
      ]}
    />
  );
}
