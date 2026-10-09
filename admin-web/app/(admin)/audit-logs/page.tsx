"use client";

import PlatformResource from "@/components/platform/PlatformResource";

export default function AuditLogsPage() {
  return (
    <PlatformResource
      title="Audit logs"
      description="Activity from /api/v1/super-admin/audit-logs"
      endpoint="/super-admin/audit-logs"
      columns={[
        { key: "id", label: "ID" },
        { key: "action", label: "Action" },
        { key: "entity_type", label: "Entity" },
        { key: "entity_id", label: "Entity ID" },
        { key: "actor_email", label: "Actor" },
        { key: "school_id", label: "School" },
        { key: "created_at", label: "When" },
      ]}
    />
  );
}
