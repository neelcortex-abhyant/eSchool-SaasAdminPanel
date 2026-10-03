"use client";

import ResourceList from "@/components/ResourceList";

type Package = {
  id: number;
  name: string | null;
  description: string | null;
  status: string | number | null;
};

export default function PackagesPage() {
  return (
    <ResourceList<Package>
      title="Packages"
      endpoint="/packages"
      columns={[
        { key: "id", label: "ID" },
        { key: "name", label: "Name" },
        { key: "description", label: "Description" },
        { key: "status", label: "Status" },
      ]}
    />
  );
}
