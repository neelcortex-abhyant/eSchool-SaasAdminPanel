"use client";

import PlatformResource from "@/components/platform/PlatformResource";

export default function AddonsPage() {
  return (
    <PlatformResource
      title="Addons"
      description="Add-ons from /api/v1/super-admin/addons"
      endpoint="/super-admin/addons"
      canCreate
      canEdit
      statusToggle
      columns={[
        { key: "id", label: "ID" },
        { key: "name", label: "Name" },
        { key: "price", label: "Price" },
        { key: "status", label: "Status" },
        { key: "description", label: "Description" },
      ]}
      fields={[
        { key: "name", label: "Name", required: true },
        { key: "description", label: "Description", type: "textarea" },
        { key: "price", label: "Price", type: "number" },
      ]}
    />
  );
}
