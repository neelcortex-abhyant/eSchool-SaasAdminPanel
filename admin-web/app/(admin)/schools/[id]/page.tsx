"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { SchoolBilling } from "@/components/schools/SchoolBilling";
import { loadSchool, loadSchoolAdmins, schoolStatusLabel, type SchoolAdmin, type SchoolRecord } from "@/lib/school";

type ConfirmAction = "delete" | "suspend" | "deactivate";

export default function SchoolProfilePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [school, setSchool] = useState<SchoolRecord | null>(null);
  const [admins, setAdmins] = useState<SchoolAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState("");
  const [confirm, setConfirm] = useState<ConfirmAction | null>(null);
  const [logoFailed, setLogoFailed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setNotFound(false);
    setLogoFailed(false);
    const result = await loadSchool(params.id);
    if (result.status === 404) {
      setSchool(null);
      setAdmins([]);
      setNotFound(true);
      setLoading(false);
      return;
    }
    if (!result.ok || !result.data?.id) {
      setSchool(null);
      setAdmins([]);
      setError(
        result.status === 403
          ? "This account cannot manage schools. Sign in with a super admin account."
          : apiErrorMessage(result.data, "Unable to load this school."),
      );
      setLoading(false);
      return;
    }
    setSchool(result.data);
    const adminResult = await loadSchoolAdmins(params.id);
    setAdmins(adminResult.ok ? adminResult.data.items || [] : []);
    setLoading(false);
  }, [params.id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function runAction(action: "activate" | "suspend" | "deactivate" | "provision" | "delete") {
    if (!school) return;
    setPending(action);
    setError("");
    setNotice("");
    const result =
      action === "delete"
        ? await api(`/super-admin/schools/${school.id}`, { method: "DELETE" })
        : await api(`/super-admin/schools/${school.id}/${action}`, { method: "POST" });
    setPending("");
    setConfirm(null);
    if (!result.ok) {
      setError(apiErrorMessage(result.data, "Unable to update this school."));
      return;
    }
    if (action === "delete") {
      router.push("/schools");
      return;
    }
    setNotice("School updated.");
    await load();
  }

  return (
    <div>
      {loading ? <ProfileSkeleton /> : null}

      {!loading && notFound ? (
        <section className="panel-card">
          <div className="empty-state">This school was not found.</div>
          <div className="page-actions">
            <Link className="btn-pill btn-pill-green" href="/schools">
              Back to schools
            </Link>
          </div>
        </section>
      ) : null}

      {!loading && error && !school ? (
        <section className="panel-card">
          <div className="alert alert-danger">{error}</div>
          <div className="page-actions">
            <button className="btn-pill btn-pill-green" type="button" onClick={() => void load()}>
              Retry
            </button>
            <Link className="btn-pill btn-pill-green-soft" href="/schools">
              Back to schools
            </Link>
          </div>
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
                  <span className={`status-badge ${school.deleted_at ? "failed" : school.status === 1 ? "paid" : "pending"}`}>
                    {school.deleted_at ? "Deleted" : schoolStatusLabel(school.status)}
                  </span>
                  <span className={`status-badge ${school.installed === 1 ? "paid" : "pending"}`}>
                    {school.installed === 1 ? "Installed" : "Not installed"}
                  </span>
                </div>
              </div>
            </div>
            <div className="school-profile-actions">
              <Link className="btn-pill btn-pill-green-soft" href="/schools">
                Back to schools
              </Link>
              <Link className="btn-pill btn-pill-green" href={`/schools/${school.id}/edit`}>
                Edit school
              </Link>
              {school.status === 1 ? (
                <button className="btn-pill btn-pill-green-soft" type="button" onClick={() => setConfirm("suspend")}>
                  Suspend
                </button>
              ) : (
                <button className="btn-pill btn-pill-green" type="button" disabled={pending !== ""} onClick={() => void runAction("activate")}>
                  {pending === "activate" ? "Saving…" : "Activate"}
                </button>
              )}
              <button className="btn-pill btn-pill-green-soft" type="button" disabled={pending !== ""} onClick={() => void runAction("provision")}>
                {pending === "provision" ? "Saving…" : "Provision"}
              </button>
              <button className="btn-pill btn-pill-danger" type="button" onClick={() => setConfirm("deactivate")}>
                Deactivate
              </button>
              <button className="btn-pill btn-pill-danger" type="button" onClick={() => setConfirm("delete")}>
                Delete school
              </button>
            </div>
          </header>

          {error ? <div className="alert alert-danger">{error}</div> : null}
          {notice ? <div className="alert alert-info">{notice}</div> : null}

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
                <Item label="Status" value={school.deleted_at ? "Deleted" : schoolStatusLabel(school.status)} />
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
                <Item label="Logo" value={school.logo} />
                <Item label="Legacy admin ID" value={school.admin_id} />
                <Item label="Platform admin ID" value={school.v1_admin_id} />
                <Item label="Database name" value={school.database_name} />
                <Item label="Provisioned" value={formatWhen(school.provisioned_at)} />
                <Item label="Created" value={formatWhen(school.created_at)} />
                <Item label="Updated" value={formatWhen(school.updated_at)} />
              </dl>
            </article>
            <article className="panel-card">
              <div className="panel-card-header">
                <h2>School admins</h2>
              </div>
              {admins.length ? (
                admins.map((admin) => (
                  <dl className="school-detail" key={admin.id} style={{ marginBottom: 16 }}>
                    <Item label="Name" value={`${admin.first_name} ${admin.last_name}`.trim()} />
                    <Item label="Email" value={admin.email} />
                    <Item label="Mobile" value={admin.mobile} />
                    <Item label="Status" value={admin.status === 1 ? "Active" : "Inactive"} />
                  </dl>
                ))
              ) : (
                <div className="empty-state">No school admin is linked to this school.</div>
              )}
            </article>
          </section>

          <SchoolBilling schoolId={school.id} />
        </>
      ) : null}

      {confirm && school ? (
        <ConfirmDialog
          title={confirmTitle(confirm)}
          body={`This will ${confirm} ${school.name || "this school"}.`}
          confirmLabel={pending === confirm ? "Saving…" : confirmTitle(confirm)}
          busy={pending !== ""}
          onCancel={() => setConfirm(null)}
          onConfirm={() => void runAction(confirm)}
        />
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
  const showImage = logo && !failed && (logo.startsWith("http") || logo.startsWith("/") || logo.startsWith("data:"));
  if (showImage) {
    return <img className="school-avatar" src={logo} alt="" onError={onError} />;
  }
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

function confirmTitle(action: ConfirmAction): string {
  if (action === "delete") return "Delete school";
  if (action === "suspend") return "Suspend school";
  return "Deactivate school";
}

function ConfirmDialog({
  title,
  body,
  confirmLabel,
  busy,
  onCancel,
  onConfirm,
}: {
  title: string;
  body: string;
  confirmLabel: string;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="confirm-title">{title}</h2>
        <p>{body}</p>
        <div className="resource-actions">
          <button className="btn-pill btn-pill-danger" type="button" disabled={busy} onClick={onConfirm}>
            {confirmLabel}
          </button>
          <button className="btn-pill btn-pill-green-soft" type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
