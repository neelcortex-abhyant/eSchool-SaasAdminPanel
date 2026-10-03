"use client";

import ResourceList from "@/components/ResourceList";

type Announcement = {
  id: number;
  title: string | null;
  description: string | null;
};

export default function AnnouncementsPage() {
  return (
    <ResourceList<Announcement>
      title="Announcements"
      endpoint="/announcements"
      columns={[
        { key: "id", label: "ID" },
        { key: "title", label: "Title" },
        { key: "description", label: "Description" },
      ]}
    />
  );
}
