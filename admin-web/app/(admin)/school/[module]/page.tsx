"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import SchoolModulePage from "@/components/school-admin/SchoolModulePage";

/** Old menu slugs now served by the Academic structure pages. */
const MOVED: Record<string, string> = {
  medium: "/school/academics/mediums",
  class: "/school/academics/classes",
  section: "/school/academics/sections",
  subject: "/school/academics/subjects",
  "class-subject": "/school/academics/subjects",
  "class-section-teachers": "/school/academics/teacher-assignments",
};

export default function SchoolModuleRoute() {
  const params = useParams<{ module: string }>();
  const router = useRouter();
  const moved = MOVED[params.module];

  useEffect(() => {
    if (moved) router.replace(moved);
  }, [moved, router]);

  if (moved) return null;
  return <SchoolModulePage moduleKey={params.module} />;
}
