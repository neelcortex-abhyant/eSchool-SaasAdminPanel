"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { apiErrorMessage } from "@/lib/api";
import { loadSchool } from "@/lib/school";
import { PageHeading } from "@/components/dashboard/StatCard";
import { SchoolForm } from "@/components/schools/SchoolForm";
import type { SchoolFormValues } from "@/lib/schoolForm";
import { IconBuilding } from "@/lib/icons";

export default function EditSchoolPage() {
  const params = useParams<{ id: string }>();
  const [initial, setInitial] = useState<SchoolFormValues | null>(null);
  const [schoolId, setSchoolId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setNotFound(false);
    setInitial(null);
    const result = await loadSchool(params.id);
    if (result.status === 404) {
      setNotFound(true);
      setLoading(false);
      return;
    }
    if (!result.ok || !result.data.id) {
      setError(
        result.status === 403
          ? "This account cannot edit schools. Sign in with a super admin account."
          : apiErrorMessage(result.data, "Unable to load this school."),
      );
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
      logo: school.logo || "",
      domain: school.domain || "",
      status: school.status === 0 ? "0" : "1",
      admin_first_name: "",
      admin_last_name: "",
      admin_password: "",
    });
    setLoading(false);
  }, [params.id]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <PageHeading
        title="Edit school"
        description="Update the saved school details"
        icon={<IconBuilding width={20} height={20} />}
      />
      {notFound ? (
        <section className="panel-card">
          <div className="empty-state">This school was not found.</div>
          <div className="page-actions">
            <Link className="btn-pill btn-pill-green" href="/schools">
              Back to schools
            </Link>
          </div>
        </section>
      ) : null}
      {error ? (
        <section className="panel-card">
          <div className="alert alert-danger">{error}</div>
          <div className="page-actions">
            <button className="btn-pill btn-pill-green" type="button" onClick={() => void load()}>
              Retry
            </button>
          </div>
        </section>
      ) : null}
      {loading ? (
        <div className="panel-card">
          <div className="skeleton" style={{ height: 180 }} />
        </div>
      ) : null}
      {!loading && initial && schoolId ? <SchoolForm mode="edit" initial={initial} schoolId={schoolId} /> : null}
    </div>
  );
}
