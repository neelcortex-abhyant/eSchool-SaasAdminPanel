"use client";

import PlatformResource from "@/components/platform/PlatformResource";

export default function ReportsPage() {
  return (
    <div>
      <PlatformResource
        title="School report"
        description="From /api/v1/super-admin/reports/schools"
        endpoint="/super-admin/reports/schools"
        columns={[
          { key: "id", label: "ID" },
          { key: "name", label: "Name" },
          { key: "code", label: "Code" },
          { key: "status", label: "Status" },
          { key: "installed", label: "Installed" },
          { key: "created_at", label: "Created" },
        ]}
      />
      <div style={{ height: 24 }} />
      <PlatformResource
        title="Subscription report"
        description="From /api/v1/super-admin/reports/subscriptions"
        endpoint="/super-admin/reports/subscriptions"
        columns={[
          { key: "id", label: "ID" },
          { key: "school_id", label: "School" },
          { key: "package_id", label: "Plan" },
          { key: "status", label: "Status" },
          { key: "cycle", label: "Cycle" },
          { key: "start_date", label: "Start" },
          { key: "end_date", label: "End" },
        ]}
      />
      <div style={{ height: 24 }} />
      <PlatformResource
        title="Bill report"
        description="From /api/v1/super-admin/reports/bills"
        endpoint="/super-admin/reports/bills"
        columns={[
          { key: "id", label: "ID" },
          { key: "school_id", label: "School" },
          { key: "subscription_id", label: "Subscription" },
          { key: "amount", label: "Amount" },
          { key: "status", label: "Status" },
          { key: "due_date", label: "Due" },
        ]}
      />
    </div>
  );
}
