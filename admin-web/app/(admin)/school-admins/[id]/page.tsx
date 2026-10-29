"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { RolePermissionsEditor } from "@/components/school-admins/RolePermissionsEditor";
import { apiErrorMessage } from "@/lib/api";
import {
  getSchoolAdminUser,
  schoolAdminDisplayName,
  schoolAdminStatusLabel,
  sendSchoolAdminPasswordReset,
  setSchoolAdminStatus,
} from "@/lib/schoolAdminUsers/api";
import type { SchoolAdminUser } from "@/lib/schoolAdminUsers/types";

type StatusAction = "activate" | "deactivate";

export default function SchoolAdminProfilePage() {
  const params = useParams<{ id: string }>();
  const [admin, setAdmin] = useState<SchoolAdminUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [statusConfirm, setStatusConfirm] = useState<StatusAction | null>(null);
  const [resetConfirm, setResetConfirm] = useState(false);
  const [pending, setPending] = useState("");

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
      setError(
        result.status === 403
          ? "You do not have permission to view this school admin."
          : apiErrorMessage(result.data, "Unable to load this profile."),
      );
      setLoading(false);
      return;
    }
    setAdmin(result.data);
    setLoading(false);
  }, [params.id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function runStatusChange() {
    if (!admin || !statusConfirm) return;
    setPending(statusConfirm);
    setNotice("");
    setError("");
    const status = statusConfirm === "activate" ? 1 : 0;
    const result = await setSchoolAdminStatus(admin.id, status);
    setPending("");
    setStatusConfirm(null);
    if (!result.ok) {
      setError(apiErrorMessage(result.data, "Unable to update account status."));
      return;
    }
    setNotice(status === 1 ? "Account activated." : "Account deactivated.");
    await load();
  }

  async function runPasswordReset() {
    if (!admin) return;
    setPending("reset");
    setNotice("");
    setError("");
    const result = await sendSchoolAdminPasswordReset(admin.id, admin.email);
    setPending("");
    setResetConfirm(false);
    if (!result.ok) {
      setError(apiErrorMessage(result.data, "Unable to send password reset link."));
      return;
    }
    setNotice("Password reset / invitation email sent. No credentials are shown in the admin panel.");
  }

  return (
    <div>
      <Suspense fallback={null}>
        <QueryNotices />
      </Suspense>

      {loading ? <ProfileSkeleton /> : null}

      {!loading && notFound ? (
        <section className="panel-card">
          <div className="empty-state">This school admin was not found or is not accessible.</div>
          <Link className="btn-pill btn-pill-green" href="/school-admins">
            Back to school admins
          </Link>
        </section>
      ) : null}

      {!loading && error && !admin ? (
        <section className="panel-card">
          <div className="alert alert-danger">{error}</div>
          <button className="btn-pill btn-pill-green" type="button" onClick={() => void load()}>
            Retry
          </button>
        </section>
      ) : null}

      {!loading && admin ? (
        <>
          <header className="school-profile-header">
            <div className="school-profile-identity">
              <div className="school-avatar">{initials(admin)}</div>
              <div>
                <h1>{schoolAdminDisplayName(admin)}</h1>
                <div className="school-profile-meta">
                  <span>{admin.email}</span>
                  <span className={`status-badge ${admin.status === 1 ? "paid" : "pending"}`}>
                    {schoolAdminStatusLabel(admin.status)}
                  </span>
                  <span className="muted">{admin.role_label}</span>
                </div>
              </div>
            </div>
            <div className="school-profile-actions">
              <Link className="btn-pill btn-pill-green-soft" href="/school-admins">
                Back to list
              </Link>
              <Link className="btn-pill btn-pill-green" href={`/school-admins/${admin.id}/edit`}>
                Edit profile
              </Link>
              <Link className="btn-pill btn-pill-green-soft" href={`/school-admins/${admin.id}/roles`}>
                Roles &amp; permissions
              </Link>
              {admin.status === 1 ? (
                <button className="btn-pill btn-pill-green-soft" type="button" onClick={() => setStatusConfirm("deactivate")}>
                  Deactivate
                </button>
              ) : (
                <button className="btn-pill btn-pill-green" type="button" onClick={() => setStatusConfirm("activate")}>
                  Activate
                </button>
              )}
              <button className="btn-pill btn-pill-green-soft" type="button" onClick={() => setResetConfirm(true)}>
                Send password reset link
              </button>
              <Link className="link-btn" href={`/schools/${admin.school_id}`}>
                View school
              </Link>
            </div>
          </header>

          {notice ? <div className="alert alert-success">{notice}</div> : null}
          {error ? <div className="alert alert-danger">{error}</div> : null}

          <section className="panel-grid">
            <article className="panel-card">
              <div className="panel-card-header">
                <h2>Profile</h2>
              </div>
              <dl className="school-detail">
                <Item label="Full name" value={schoolAdminDisplayName(admin)} />
                <Item label="Email" value={admin.email} />
                <Item label="Phone" value={admin.mobile} />
                <Item label="School" value={admin.school_name} />
                <Item label="Role" value={admin.role_label} />
                <Item label="Status" value={schoolAdminStatusLabel(admin.status)} />
                <Item label="Created" value={formatWhen(admin.created_at)} />
                <Item label="Last login" value={admin.last_login_at ? formatWhen(admin.last_login_at) : "—"} />
              </dl>
            </article>
          </section>

          <RolePermissionsEditor admin={admin} />
        </>
      ) : null}

      {statusConfirm && admin ? (
        <ConfirmDialog
          title={statusConfirm === "activate" ? "Activate account" : "Deactivate account"}
          body={
            statusConfirm === "activate"
              ? `Activate ${schoolAdminDisplayName(admin)}? They will be able to sign in when the backend allows it.`
              : `Deactivate ${schoolAdminDisplayName(admin)}? Active sessions may be revoked by the server.`
          }
          confirmLabel={statusConfirm === "activate" ? "Activate" : "Deactivate"}
          pending={pending !== ""}
          onCancel={() => setStatusConfirm(null)}
          onConfirm={() => void runStatusChange()}
        />
      ) : null}

      {resetConfirm && admin ? (
        <ConfirmDialog
          title="Send password reset link"
          body={`Send a secure password-setup or reset link to ${admin.email}? Tokens and passwords are never shown here.`}
          confirmLabel="Send link"
          pending={pending === "reset"}
          onCancel={() => setResetConfirm(false)}
          onConfirm={() => void runPasswordReset()}
        />
      ) : null}
    </div>
  );
}

function QueryNotices() {
  const searchParams = useSearchParams();
  const created = searchParams.get("created");
  const saved = searchParams.get("saved");
  if (created === "1") return <div className="alert alert-success">School admin created successfully.</div>;
  if (saved === "1") return <div className="alert alert-success">Profile updated.</div>;
  return null;
}

function Item({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value === null || value === undefined || value === "" ? "—" : String(value)}</dd>
    </div>
  );
}

function formatWhen(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function initials(admin: SchoolAdminUser): string {
  const parts = [admin.first_name, admin.last_name].filter(Boolean);
  return parts.map((p) => p[0]?.toUpperCase() || "").join("") || "A";
}

function ProfileSkeleton() {
  return (
    <div>
      <div className="school-profile-header">
        <div className="skeleton" style={{ height: 72, width: "100%" }} />
      </div>
      <div className="panel-card skeleton" style={{ height: 200, marginTop: 16 }} />
    </div>
  );
}
