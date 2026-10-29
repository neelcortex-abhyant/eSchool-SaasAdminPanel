"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { loadSchools, schoolStatusLabel, type SchoolRecord } from "@/lib/school";
import { PageHeading } from "@/components/dashboard/StatCard";
import { IconBuilding } from "@/lib/icons";

const PAGE_SIZE = 20;

type StatusFilter = "" | "0" | "1";
type SortKey = "name" | "created_at";
type SortOrder = "asc" | "desc";
type StatusAction = "activate" | "deactivate";

export default function SchoolsPage() {
  const [rows, setRows] = useState<SchoolRecord[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("");
  const [sort, setSort] = useState<SortKey>("created_at");
  const [order, setOrder] = useState<SortOrder>("desc");
  const [confirm, setConfirm] = useState<{ school: SchoolRecord; action: StatusAction } | null>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const result = await loadSchools({ page, pageSize: PAGE_SIZE, q: search, status, sort, order });
    if (!result.ok) {
      setError(
        result.status === 401
          ? "Sign in again to manage schools."
          : result.status === 403
            ? "This account cannot manage schools. Sign in with a super admin account."
            : apiErrorMessage(result.data, "Unable to load schools."),
      );
      setRows([]);
      setTotal(0);
    } else {
      const items = result.data.items || [];
      const nextTotal = result.data.total || 0;
      const lastPage = Math.max(1, Math.ceil(nextTotal / PAGE_SIZE));
      if (items.length === 0 && page > lastPage) {
        setPage(lastPage);
        return;
      }
      setRows(items);
      setTotal(nextTotal);
    }
    setLoading(false);
  }, [page, search, status, sort, order]);

  useEffect(() => {
    void load();
  }, [load]);

  function toggleSort(column: SortKey) {
    if (sort === column) setOrder((current) => (current === "asc" ? "desc" : "asc"));
    else {
      setSort(column);
      setOrder(column === "name" ? "asc" : "desc");
    }
    setPage(1);
  }

  function resetFilters() {
    setSearchInput("");
    setSearch("");
    setStatus("");
    setSort("created_at");
    setOrder("desc");
    setPage(1);
  }

  async function runStatusChange() {
    if (!confirm) return;
    const { school, action } = confirm;
    setPendingId(school.id);
    setNotice("");
    setError("");
    const result = await api(`/super-admin/schools/${school.id}/${action}`, { method: "POST" });
    setPendingId(null);
    setConfirm(null);
    if (!result.ok) {
      setError(
        result.status === 401
          ? "Sign in again to manage schools."
          : result.status === 403
            ? "This account cannot change school status."
            : apiErrorMessage(result.data, "Unable to update this school."),
      );
      return;
    }
    setNotice(action === "activate" ? "School activated." : "School deactivated.");
    await load();
  }

  const filtered = Boolean(search || status);
  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <PageHeading
        title="Schools"
        description="Registered schools on the platform"
        icon={<IconBuilding width={20} height={20} />}
      />
      <div className="page-actions">
        <Link className="btn-pill btn-pill-green" href="/schools/new">
          Add school
        </Link>
      </div>
      <div className="school-filters">
        <input
          type="search"
          aria-label="Search schools by name or code"
          placeholder="Search by name or code"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
        />
        <select
          aria-label="Filter by status"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value as StatusFilter);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          <option value="1">Active</option>
          <option value="0">Inactive</option>
        </select>
        <button className="btn-pill btn-pill-green-soft" type="button" onClick={resetFilters}>
          Reset
        </button>
      </div>
      {notice ? <div className="alert alert-success">{notice}</div> : null}
      {error ? (
        <div className="alert alert-danger">
          {error}{" "}
          <button className="link-btn" type="button" onClick={() => void load()}>
            Retry
          </button>
        </div>
      ) : null}
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
                  <th>
                    <button type="button" className="sort-btn" onClick={() => toggleSort("name")}>
                      Name {sort === "name" ? (order === "asc" ? "↑" : "↓") : ""}
                    </button>
                  </th>
                  <th>Code</th>
                  <th>Contact</th>
                  <th>Status</th>
                  <th>
                    <button type="button" className="sort-btn" onClick={() => toggleSort("created_at")}>
                      Created {sort === "created_at" ? (order === "asc" ? "↑" : "↓") : ""}
                    </button>
                  </th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={6}>
                      <div className="empty-state">
                        {filtered ? "No schools match these filters." : "No schools yet. Add a school to see it here."}
                      </div>
                    </td>
                  </tr>
                ) : (
                  rows.map((school) => {
                    const active = school.status === 1;
                    return (
                      <tr key={school.id}>
                        <td>{school.name || "—"}</td>
                        <td className="mono">{school.code || "—"}</td>
                        <td>{contactLabel(school)}</td>
                        <td>
                          <span className={`status-badge ${active ? "paid" : "pending"}`}>
                            {schoolStatusLabel(school.status, school.installed)}
                          </span>
                        </td>
                        <td>{formatCreated(school.created_at)}</td>
                        <td className="school-row-actions">
                          <Link className="link-btn" href={`/schools/${school.id}`}>
                            View
                          </Link>
                          <Link className="link-btn" href={`/schools/${school.id}/edit`}>
                            Edit
                          </Link>
                          <button
                            type="button"
                            className="link-btn"
                            disabled={pendingId === school.id}
                            onClick={() => setConfirm({ school, action: active ? "deactivate" : "activate" })}
                          >
                            {active ? "Deactivate" : "Activate"}
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          <div className="page-actions" style={{ margin: 16 }}>
            <button className="btn-pill btn-pill-green-soft" type="button" disabled={page <= 1 || loading} onClick={() => setPage((current) => current - 1)}>
              Previous
            </button>
            <span className="muted">
              Page {page} of {lastPage} · {total} schools
            </span>
            <button
              className="btn-pill btn-pill-green-soft"
              type="button"
              disabled={page >= lastPage || loading}
              onClick={() => setPage((current) => current + 1)}
            >
              Next
            </button>
          </div>
        </div>
      ) : null}

      {confirm ? (
        <div className="modal-backdrop" role="presentation">
          <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="school-status-title">
            <h2 id="school-status-title">{confirm.action === "activate" ? "Activate school" : "Deactivate school"}</h2>
            <p>
              {confirm.action === "activate"
                ? `Activate ${confirm.school.name || "this school"}? It will be marked active.`
                : `Deactivate ${confirm.school.name || "this school"}? It will be marked inactive.`}
            </p>
            <div className="page-actions">
              <button className="btn-pill btn-pill-green" type="button" disabled={pendingId !== null} onClick={() => void runStatusChange()}>
                {pendingId !== null ? "Saving…" : "Confirm"}
              </button>
              <button className="btn-pill btn-pill-green-soft" type="button" disabled={pendingId !== null} onClick={() => setConfirm(null)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function contactLabel(school: SchoolRecord): string {
  const parts = [school.support_email, school.support_phone].filter((part) => part && part.trim());
  return parts.length ? parts.join(" · ") : "—";
}

function formatCreated(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
