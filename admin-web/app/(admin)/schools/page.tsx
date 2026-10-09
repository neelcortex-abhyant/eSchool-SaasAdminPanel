"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { loadSchools, schoolStatusLabel, type SchoolRecord } from "@/lib/school";
import { PageHeading } from "@/components/dashboard/StatCard";
import { IconBuilding } from "@/lib/icons";

export default function SchoolsPage() {
  const [rows, setRows] = useState<SchoolRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const result = await loadSchools();
    if (!result.ok) {
      setError(
        result.status === 403
          ? "This account cannot manage schools. Sign in with a super admin account."
          : apiErrorMessage(result.data, "Unable to load schools."),
      );
      setRows([]);
    } else {
      setRows(result.data.items || []);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onDelete(school: SchoolRecord) {
    if (!window.confirm(`Delete ${school.name || "this school"}?`)) return;
    setNotice("");
    setError("");
    const result = await api(`/super-admin/schools/${school.id}`, { method: "DELETE" });
    if (!result.ok) {
      setError(apiErrorMessage(result.data, "Unable to delete this school."));
      return;
    }
    setNotice("School deleted.");
    await load();
  }

  return (
    <div>
      <PageHeading
        title="Schools"
        description="Schools on the platform"
        icon={<IconBuilding width={20} height={20} />}
      />
      <div className="page-actions">
        <Link className="btn-pill btn-pill-green" href="/schools/new">
          Add school
        </Link>
      </div>
      {notice ? <div className="alert alert-info">{notice}</div> : null}
      {error ? <div className="alert alert-danger">{error}</div> : null}
      {loading ? (
        <div className="resource-card" style={{ padding: 20 }}>
          <div className="skeleton" style={{ height: 18, width: "30%", marginBottom: 16 }} />
          <div className="skeleton" style={{ height: 180 }} />
        </div>
      ) : null}
      {!loading && !error ? (
        <div className="resource-card">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Code</th>
                  <th>Support email</th>
                  <th>Phone</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={6}>
                      <div className="empty-state">No schools yet. Add a school to see it here.</div>
                    </td>
                  </tr>
                ) : (
                  rows.map((school) => (
                    <tr key={school.id}>
                      <td>{school.name || "—"}</td>
                      <td className="mono">{school.code || "—"}</td>
                      <td>{school.support_email || "—"}</td>
                      <td>{school.support_phone || "—"}</td>
                      <td>
                        <span className={`status-badge ${school.status === 1 ? "paid" : "pending"}`}>
                          {schoolStatusLabel(school.status)}
                        </span>
                      </td>
                      <td>
                        <Link className="link-btn" href={`/schools/${school.id}`}>
                          View
                        </Link>
                        {" · "}
                        <Link className="link-btn" href={`/schools/${school.id}/edit`}>
                          Edit
                        </Link>
                        {" · "}
                        <button type="button" className="link-btn" onClick={() => onDelete(school)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
