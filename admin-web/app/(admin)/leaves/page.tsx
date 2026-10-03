"use client";

import ResourceList from "@/components/ResourceList";

type Leave = {
  id: number;
  user_id: number | null;
  reason: string | null;
  status: string | null;
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
        { key: "status", label: "Status" },
      ]}
    />
  );
}
