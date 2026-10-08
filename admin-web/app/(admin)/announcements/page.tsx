"use client";

import ResourceList from "@/components/ResourceList";

type Announcement = {
  id: number;
  title: string | null;
  description: string | null;
  session_year_id: number | null;
  school_id: number | null;
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
        { key: "session_year_id", label: "Session year" },
        { key: "school_id", label: "School" },
      ]}
      fields={[
        { key: "title", label: "Title", required: true },
        { key: "description", label: "Description", type: "textarea" },
        { key: "session_year_id", label: "Session year ID", type: "number", required: true },
        { key: "school_id", label: "School ID", type: "number", required: true, createOnly: true },
      ]}
    />
  );
}
