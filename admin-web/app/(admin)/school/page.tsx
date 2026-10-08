"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { schoolStatusLabel, type SchoolRecord } from "@/lib/school";

type SchoolAdminMe = {
  id?: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  mobile?: string | null;
  role?: string;
  school_id?: number | null;
  status?: number;
};

export default function SchoolAdminPage() {
  const [school, setSchool] = useState<SchoolRecord | null>(null);
  const [admin, setAdmin] = useState<SchoolAdminMe | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState("");
  const [logoFailed, setLogoFailed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setNotFound(false);
    setLogoFailed(false);
    const [me, schoolResult] = await Promise.all([
      api<SchoolAdminMe>("/school-admin/me"),
      api<SchoolRecord>("/school-admin/school"),
    ]);
    if (me.status === 403 || schoolResult.status === 403) {
      setError("This account is not a school admin.");
      setLoading(false);
      return;
    }
    if (!me.ok) {
      setError(apiErrorMessage(me.data, "Unable to load your school admin profile."));
      setLoading(false);
      return;
    }
    setAdmin(me.data);
    if (schoolResult.status === 404) {
      setNotFound(true);
      setLoading(false);
      return;
    }
    if (!schoolResult.ok || !schoolResult.data?.id) {
      setError(apiErrorMessage(schoolResult.data, "Unable to load your school."));
      setLoading(false);
      return;
    }
    setSchool(schoolResult.data);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      {loading ? <ProfileSkeleton /> : null}

      {!loading && error ? (
        <section className="panel-card">
          <div className="alert alert-danger">{error}</div>
          <div className="page-actions">
            <button className="btn-pill btn-pill-green" type="button" onClick={() => void load()}>
              Retry
            </button>
          </div>
        </section>
      ) : null}

      {!loading && notFound ? (
        <section className="panel-card">
          <div className="empty-state">No school is assigned to this account.</div>
        </section>
      ) : null}

      {!loading && school ? (
        <>
          <header className="school-profile-header">
            <div className="school-profile-identity">
              <SchoolAvatar school={school} failed={logoFailed} onError={() => setLogoFailed(true)} />
              <div>
                <h1>{text(school.name)}</h1>
                <div className="school-profile-meta">
                  <span className="mono">{text(school.code)}</span>
                  <span className={`status-badge ${school.status === 1 ? "paid" : "pending"}`}>
                    {schoolStatusLabel(school.status)}
                  </span>
                </div>
              </div>
            </div>
            <div className="school-profile-actions">
              <Link className="btn-pill btn-pill-green" href="/settings">
                Edit my profile
              </Link>
            </div>
          </header>

          {!school.name && !school.code ? (
            <div className="panel-card">
              <div className="empty-state">This school record has no profile details yet.</div>
            </div>
          ) : null}

          <section className="panel-grid">
            <article className="panel-card">
              <div className="panel-card-header">
                <h2>School information</h2>
              </div>
              <dl className="school-detail">
                <Item label="School name" value={school.name} />
                <Item label="School code" value={school.code} />
                <Item label="Email" value={school.support_email} />
                <Item label="Phone" value={school.support_phone} />
                <Item label="Website" value={school.website || school.domain} />
                <Item label="School type" value={school.school_type} />
                <Item label="Status" value={schoolStatusLabel(school.status)} />
                <Item label="Tagline" value={school.tagline} />
              </dl>
            </article>
            <article className="panel-card">
              <div className="panel-card-header">
                <h2>Address</h2>
              </div>
              {school.address || school.city || school.state || school.country || school.postal_code ? (
                <dl className="school-detail">
                  <Item label="Full address" value={school.address} />
                  <Item label="City" value={school.city} />
                  <Item label="State" value={school.state} />
                  <Item label="Country" value={school.country} />
                  <Item label="Postal code" value={school.postal_code} />
                </dl>
              ) : (
                <div className="empty-state">No address is stored for this school.</div>
              )}
            </article>
          </section>

          <section className="panel-grid">
            <article className="panel-card">
              <div className="panel-card-header">
                <h2>Additional information</h2>
              </div>
              <dl className="school-detail">
                <Item label="School ID" value={school.id} />
                <Item label="Installed" value={school.installed === 1 ? "Yes" : "No"} />
                <Item label="Domain" value={school.domain} />
                <Item label="Provisioned" value={formatWhen(school.provisioned_at)} />
                <Item label="Created" value={formatWhen(school.created_at)} />
                <Item label="Updated" value={formatWhen(school.updated_at)} />
              </dl>
            </article>
            <article className="panel-card">
              <div className="panel-card-header">
                <h2>Signed-in admin</h2>
              </div>
              {admin ? (
                <dl className="school-detail">
                  <Item label="Name" value={`${admin.first_name || ""} ${admin.last_name || ""}`.trim()} />
                  <Item label="Email" value={admin.email} />
                  <Item label="Mobile" value={admin.mobile} />
                  <Item label="Role" value={admin.role} />
                  <Item label="Status" value={admin.status === 1 ? "Active" : "Inactive"} />
                </dl>
              ) : (
                <div className="empty-state">No admin profile was returned.</div>
              )}
            </article>
          </section>
        </>
      ) : null}
    </div>
  );
}

function SchoolAvatar({
  school,
  failed,
  onError,
}: {
  school: SchoolRecord;
  failed: boolean;
  onError: () => void;
}) {
  const logo = (school.logo || "").trim();
  const showImage = Boolean(logo) && !failed && (logo.startsWith("http") || logo.startsWith("/") || logo.startsWith("data:"));
  if (showImage) return <img className="school-avatar" src={logo} alt="" onError={onError} />;
  const parts = (school.name || "School").trim().split(/\s+/).slice(0, 2);
  const letters = parts.map((part) => part[0]?.toUpperCase() || "").join("") || "S";
  return <div className="school-avatar">{letters}</div>;
}

function ProfileSkeleton() {
  return (
    <div>
      <div className="school-profile-header">
        <div className="school-profile-identity">
          <div className="skeleton school-avatar" />
          <div>
            <div className="skeleton" style={{ height: 28, width: 220, marginBottom: 8 }} />
            <div className="skeleton" style={{ height: 16, width: 140 }} />
          </div>
        </div>
      </div>
      <section className="panel-grid">
        <div className="panel-card">
          <div className="skeleton" style={{ height: 160 }} />
        </div>
        <div className="panel-card">
          <div className="skeleton" style={{ height: 160 }} />
        </div>
      </section>
    </div>
  );
}

function Item({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{text(value)}</dd>
    </div>
  );
}

function text(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

function formatWhen(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}
