"use client";

import Link from "next/link";
import { PageHeading } from "@/components/dashboard/StatCard";
import { IconUsers } from "@/lib/icons";
import { SchoolAdminForm } from "@/components/school-admins/SchoolAdminForm";
import { EMPTY_SCHOOL_ADMIN_FORM } from "@/lib/schoolAdminUsers/types";

export default function NewSchoolAdminPage() {
  return (
    <div>
      <PageHeading
        title="Create school admin"
        description="Add a school admin account for a registered school"
        icon={<IconUsers width={20} height={20} />}
      />
      <div className="page-actions">
        <Link className="btn-pill btn-pill-green-soft" href="/school-admins">
          Back to list
        </Link>
      </div>
      <SchoolAdminForm mode="create" initial={EMPTY_SCHOOL_ADMIN_FORM} />
    </div>
  );
}
