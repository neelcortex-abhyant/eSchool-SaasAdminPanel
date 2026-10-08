"use client";

import PlatformResource from "@/components/platform/PlatformResource";

export default function NotificationsPage() {
  return (
    <PlatformResource
      title="Notifications"
      description="Notifications from /api/v1/super-admin/notifications"
      endpoint="/super-admin/notifications"
      canCreate
      statusToggle
      columns={[
        { key: "id", label: "ID" },
        { key: "title", label: "Title" },
        { key: "body", label: "Body" },
        { key: "school_id", label: "School" },
        { key: "status", label: "Status" },
      ]}
      fields={[
        { key: "title", label: "Title", required: true },
        { key: "body", label: "Body", type: "textarea" },
        { key: "school_id", label: "School ID", type: "number" },
      ]}
    />
  );
}
