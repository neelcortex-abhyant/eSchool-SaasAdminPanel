"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { PageHeading } from "@/components/dashboard/StatCard";
import { IconUsers } from "@/lib/icons";
import { SchoolAdminForm, schoolAdminToFormValues } from "@/components/school-admins/SchoolAdminForm";
import { getSchoolAdminUser, schoolAdminDisplayName } from "@/lib/schoolAdminUsers/api";
import { apiErrorMessage } from "@/lib/api";
import type { SchoolAdminUser } from "@/lib/schoolAdminUsers/types";

export default function EditSchoolAdminPage() {
  const params = useParams<{ id: string }>();
  const [admin, setAdmin] = useState<SchoolAdminUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setNotFound(false);
    const result = await getSchoolAdminUser(params.id);
    if (result.status === 404) {
      setAdmin(null);
      setNotFound(true);
      setLoading(false);
      return;
    }
    if (!result.ok || !result.data.id) {
      setAdmin(null);
      setError(apiErrorMessage(result.data, "Unable to load this school admin."));
      setLoading(false);
      return;
    }
    setAdmin(result.data);
    setLoading(false);
  }, [params.id]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <PageHeading
        title="Edit school admin"
        description={admin ? schoolAdminDisplayName(admin) : "Update school admin profile"}
        icon={<IconUsers width={20} height={20} />}
      />
      <div className="page-actions">
        <Link className="btn-pill btn-pill-green-soft" href={admin ? `/school-admins/${admin.id}` : "/school-admins"}>
          Cancel
        </Link>
      </div>

      {loading ? <div className="panel-card skeleton" style={{ height: 240 }} /> : null}
      {!loading && notFound ? (
        <section className="panel-card">
          <div className="empty-state">This school admin was not found.</div>
          <Link className="btn-pill btn-pill-green" href="/school-admins">
            Back to list
          </Link>
        </section>
      ) : null}
      {!loading && error ? (
        <section className="panel-card">
          <div className="alert alert-danger">{error}</div>
          <button className="btn-pill btn-pill-green" type="button" onClick={() => void load()}>
            Retry
          </button>
        </section>
      ) : null}
      {!loading && admin ? (
        <SchoolAdminForm mode="edit" initial={schoolAdminToFormValues(admin)} adminId={admin.id} existingEmail={admin.email} />
      ) : null}
    </div>
  );
}
