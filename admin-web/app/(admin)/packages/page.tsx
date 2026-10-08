"use client";

import PlatformResource from "@/components/platform/PlatformResource";

export default function PlansPage() {
  return (
    <PlatformResource
      title="Plans"
      description="Subscription plans from /api/v1/super-admin/plans"
      endpoint="/super-admin/plans"
      canCreate
      canEdit
      statusToggle
      columns={[
        { key: "id", label: "ID" },
        { key: "name", label: "Name" },
        { key: "monthly_price", label: "Monthly" },
        { key: "yearly_price", label: "Yearly" },
        { key: "student_limit", label: "Student limit" },
        { key: "staff_limit", label: "Staff limit" },
        { key: "status", label: "Status" },
      ]}
      fields={[
        { key: "name", label: "Name", required: true },
        { key: "description", label: "Description", type: "textarea" },
        { key: "monthly_price", label: "Monthly price", type: "number" },
        { key: "yearly_price", label: "Yearly price", type: "number" },
        { key: "student_limit", label: "Student limit", type: "number" },
        { key: "staff_limit", label: "Staff limit", type: "number" },
      ]}
    />
  );
}
