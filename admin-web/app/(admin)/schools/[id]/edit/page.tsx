"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiErrorMessage } from "@/lib/api";
import { loadSchool } from "@/lib/school";
import { PageHeading } from "@/components/dashboard/StatCard";
import { SchoolForm, type SchoolFormValues } from "@/components/schools/SchoolForm";
import { IconBuilding } from "@/lib/icons";

export default function EditSchoolPage() {
  const params = useParams<{ id: string }>();
  const [initial, setInitial] = useState<SchoolFormValues | null>(null);
  const [schoolId, setSchoolId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const result = await loadSchool(params.id);
      if (cancelled) return;
      if (!result.ok || !result.data.id) {
        setError(apiErrorMessage(result.data, "Unable to load this school."));
        setLoading(false);
        return;
      }
      const school = result.data;
      setSchoolId(school.id);
      setInitial({
        name: school.name || "",
        code: school.code || "",
        address: school.address || "",
        support_email: school.support_email || "",
        support_phone: school.support_phone || "",
        tagline: school.tagline || "",
        domain: school.domain || "",
        status: school.status === 0 ? "0" : "1",
        admin_first_name: "",
        admin_last_name: "",
        admin_password: "",
      });
      setLoading(false);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  return (
    <div>
      <PageHeading
        title="Edit school"
        description="Update the saved school details"
        icon={<IconBuilding width={20} height={20} />}
      />
      {error ? <div className="alert alert-danger">{error}</div> : null}
      {loading ? (
        <div className="panel-card">
          <div className="skeleton" style={{ height: 180 }} />
        </div>
      ) : null}
      {!loading && initial && schoolId ? <SchoolForm mode="edit" initial={initial} schoolId={schoolId} /> : null}
    </div>
  );
}
