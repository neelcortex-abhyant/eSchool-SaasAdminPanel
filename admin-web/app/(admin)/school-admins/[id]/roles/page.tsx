"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { PageHeading } from "@/components/dashboard/StatCard";
import { IconUsers } from "@/lib/icons";
import { RolePermissionsEditor } from "@/components/school-admins/RolePermissionsEditor";
import { getSchoolAdminUser, schoolAdminDisplayName } from "@/lib/schoolAdminUsers/api";
import { apiErrorMessage } from "@/lib/api";
import type { SchoolAdminUser } from "@/lib/schoolAdminUsers/types";

export default function SchoolAdminRolesPage() {
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
      setNotFound(true);
      setAdmin(null);
      setLoading(false);
      return;
    }
    if (!result.ok) {
      setError(apiErrorMessage(result.data, "Unable to load school admin."));
      setAdmin(null);
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
        title="Roles & permissions"
        description={admin ? schoolAdminDisplayName(admin) : "Manage assigned role and module permissions"}
        icon={<IconUsers width={20} height={20} />}
      />
      <div className="page-actions">
        <Link className="btn-pill btn-pill-green-soft" href={admin ? `/school-admins/${admin.id}` : "/school-admins"}>
          Back to profile
        </Link>
      </div>

      {loading ? <div className="panel-card skeleton" style={{ height: 200 }} /> : null}
      {!loading && notFound ? (
        <section className="panel-card">
          <div className="empty-state">This school admin was not found.</div>
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
      {!loading && admin ? <RolePermissionsEditor admin={admin} /> : null}
    </div>
  );
}
