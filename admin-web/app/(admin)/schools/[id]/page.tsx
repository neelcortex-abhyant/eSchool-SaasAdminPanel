"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { adminApi, adminErrorMessage } from "@/lib/adminApi";
import { loadSchool, schoolStatusLabel, type SchoolRecord } from "@/lib/school";
import { PageHeading } from "@/components/dashboard/StatCard";
import { IconBuilding } from "@/lib/icons";

export default function SchoolProfilePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [school, setSchool] = useState<SchoolRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const result = await loadSchool(params.id);
      if (cancelled) return;
      if (!result.ok || !result.data.data) {
        setError(adminErrorMessage(result.data, "Unable to load this school."));
        setLoading(false);
        return;
      }
      setSchool(result.data.data);
      setLoading(false);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  async function onDelete() {
    if (!school || !window.confirm(`Delete ${school.name || "this school"}?`)) return;
    setDeleting(true);
    setError("");
    const result = await adminApi(`/schools/${school.id}`, { method: "DELETE" });
    setDeleting(false);
    if (!result.ok) {
      setError(adminErrorMessage(result.data, "Unable to delete this school."));
      return;
    }
    router.push("/schools");
  }

  return (
    <div>
      <PageHeading
        title={school?.name || "School profile"}
        description={school?.tagline || "School details"}
        icon={<IconBuilding width={20} height={20} />}
      />
      <div className="page-actions">
        <Link className="btn-pill btn-pill-green-soft" href="/schools">
          All schools
        </Link>
        {school ? (
          <Link className="btn-pill btn-pill-green" href={`/schools/${school.id}/edit`}>
            Edit school
          </Link>
        ) : null}
        {school ? (
          <button className="btn-pill btn-pill-green-soft" type="button" onClick={onDelete} disabled={deleting}>
            {deleting ? "Deleting…" : "Delete school"}
          </button>
        ) : null}
      </div>
      {error ? <div className="alert alert-danger">{error}</div> : null}
      {loading ? (
        <div className="panel-card">
          <div className="skeleton" style={{ height: 18, width: "40%", marginBottom: 16 }} />
          <div className="skeleton" style={{ height: 160 }} />
        </div>
      ) : null}
      {!loading && school ? (
        <>
          <section className="stat-grid" aria-label="School counts">
            <Count label="Students" value={school.counts?.students} />
            <Count label="Classes" value={school.counts?.classes} />
            <Count label="Subjects" value={school.counts?.subjects} />
            <Count label="Exams" value={school.counts?.exams} />
            <Count label="Fees" value={school.counts?.fees} />
            <Count label="Announcements" value={school.counts?.announcements} />
          </section>
          <section className="panel-grid">
            <article className="panel-card">
              <div className="panel-card-header">
                <h2>School information</h2>
                <span className={`status-badge ${school.status === 1 ? "paid" : "pending"}`}>
                  {schoolStatusLabel(school.status)}
                </span>
              </div>
              <dl className="school-detail">
                <Item label="School code" value={school.code} />
                <Item label="Support email" value={school.support_email} />
                <Item label="Support phone" value={school.support_phone} />
                <Item label="Address" value={school.address} />
                <Item label="Domain" value={school.domain} />
                <Item label="Installed" value={school.installed === 1 ? "Yes" : "No"} />
                <Item label="Created" value={school.created_at} />
                <Item label="Updated" value={school.updated_at} />
              </dl>
            </article>
            <article className="panel-card">
              <div className="panel-card-header">
                <h2>School admin</h2>
              </div>
              {school.admin ? (
                <dl className="school-detail">
                  <Item label="Name" value={`${school.admin.first_name} ${school.admin.last_name}`} />
                  <Item label="Email" value={school.admin.email} />
                  <Item label="Mobile" value={school.admin.mobile} />
                </dl>
              ) : (
                <div className="empty-state">No school admin is linked to this school.</div>
              )}
            </article>
          </section>
        </>
      ) : null}
    </div>
  );
}

function Item({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value === null || value === undefined || value === "" ? "—" : String(value)}</dd>
    </div>
  );
}

function Count({ label, value }: { label: string; value: number | undefined }) {
  return (
    <article className="stat-card">
      <p className="stat-title">{label}</p>
      <p className="stat-value">{value ?? 0}</p>
    </article>
  );
}
