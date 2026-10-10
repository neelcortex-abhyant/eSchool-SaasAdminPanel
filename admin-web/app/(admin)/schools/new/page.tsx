"use client";

import { PageHeading } from "@/components/dashboard/StatCard";
import { SchoolForm } from "@/components/schools/SchoolForm";
import { EMPTY_SCHOOL_FORM } from "@/lib/schoolForm";
import { IconBuilding } from "@/lib/icons";

export default function NewSchoolPage() {
  return (
    <div>
      <PageHeading
        title="Create school"
        description="Add a school and its admin account"
        icon={<IconBuilding width={20} height={20} />}
      />
      <SchoolForm mode="create" initial={EMPTY_SCHOOL_FORM} />
    </div>
  );
}
