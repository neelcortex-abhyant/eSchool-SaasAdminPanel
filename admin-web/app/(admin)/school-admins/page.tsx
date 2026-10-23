"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { apiErrorMessage } from "@/lib/api";
import { loadSchools, type SchoolRecord } from "@/lib/school";
import { PageHeading } from "@/components/dashboard/StatCard";
import { IconUsers } from "@/lib/icons";
import {
  listSchoolAdminUsers,
  loadSchoolAdminRoles,
  schoolAdminDisplayName,
  schoolAdminStatusLabel,
} from "@/lib/schoolAdminUsers/api";
import type { SchoolAdminUser } from "@/lib/schoolAdminUsers/types";

const PAGE_SIZE = 20;

type StatusFilter = "" | "0" | "1";
type SortKey = "name" | "created_at";
type SortOrder = "asc" | "desc";

function SchoolAdminsPageInner() {
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<SchoolAdminUser[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [schoolId, setSchoolId] = useState<string>("");
  const [roleKey, setRoleKey] = useState("");
  const [status, setStatus] = useState<StatusFilter>("");
  const [sort, setSort] = useState<SortKey>("created_at");
  const [order, setOrder] = useState<SortOrder>("desc");
  const [schools, setSchools] = useState<SchoolRecord[]>([]);
  const [roles, setRoles] = useState<{ key: string; label: string }[]>([]);

  useEffect(() => {
    const fromSchool = searchParams.get("school");
    if (fromSchool && /^\d+$/.test(fromSchool)) {
      setSchoolId(fromSchool);
    }
  }, [searchParams]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    void (async () => {
      const [schoolsResult, rolesResult] = await Promise.all([
        loadSchools({ page: 1, pageSize: 100, sort: "name", order: "asc" }),
        loadSchoolAdminRoles(),
      ]);
      if (schoolsResult.ok) setSchools(schoolsResult.data.items || []);
      if (rolesResult.ok) setRoles((rolesResult.data.items || []).map((r) => ({ key: r.key, label: r.label })));
    })();
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const result = await listSchoolAdminUsers({
      page,
      pageSize: PAGE_SIZE,
      q: search,
      school_id: schoolId ? Number(schoolId) : "",
      role_key: roleKey || undefined,
      status,
      sort,
      order,
    });
    if (!result.ok) {
      setError(
        result.status === 401
          ? "Sign in again to manage school admins."
          : result.status === 403
            ? "This account cannot manage school admins."
            : apiErrorMessage(result.data, "Unable to load school admins."),
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
  }, [page, search, schoolId, roleKey, status, sort, order]);

  useEffect(() => {
    void load();
  }, [load]);

  function toggleSort(column: SortKey) {
    if (sort === column) setOrder((c) => (c === "asc" ? "desc" : "asc"));
    else {
      setSort(column);
      setOrder(column === "name" ? "asc" : "desc");
    }
    setPage(1);
  }

  function resetFilters() {
    setSearchInput("");
    setSearch("");
    setSchoolId("");
    setRoleKey("");
    setStatus("");
    setSort("created_at");
    setOrder("desc");
    setPage(1);
  }

  const filtered = Boolean(search || schoolId || roleKey || status);
  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <PageHeading
        title="School admins"
        description="Manage school admin accounts and access across registered schools"
        icon={<IconUsers width={20} height={20} />}
      />
      <div className="page-actions">
        <Link className="btn-pill btn-pill-green" href="/school-admins/new">
          Add school admin
        </Link>
      </div>
      <div className="school-filters">
        <input
          type="search"
          aria-label="Search by name or email"
          placeholder="Search by name or email"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        <select aria-label="Filter by school" value={schoolId} onChange={(e) => { setSchoolId(e.target.value); setPage(1); }}>
          <option value="">All schools</option>
          {schools.map((s) => (
            <option key={s.id} value={String(s.id)}>
              {s.name || `School #${s.id}`}
            </option>
          ))}
        </select>
        <select aria-label="Filter by role" value={roleKey} onChange={(e) => { setRoleKey(e.target.value); setPage(1); }}>
          <option value="">All roles</option>
          {roles.map((r) => (
            <option key={r.key} value={r.key}>
              {r.label}
            </option>
          ))}
        </select>
        <select aria-label="Filter by status" value={status} onChange={(e) => { setStatus(e.target.value as StatusFilter); setPage(1); }}>
          <option value="">All statuses</option>
          <option value="1">Active</option>
          <option value="0">Inactive</option>
        </select>
        <button className="btn-pill btn-pill-green-soft" type="button" onClick={resetFilters}>
          Reset
        </button>
      </div>

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
                      Admin {sort === "name" ? (order === "asc" ? "↑" : "↓") : ""}
                    </button>
                  </th>
                  <th>Email</th>
                  <th>Phone</th>
                  <th>School</th>
                  <th>Role</th>
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
                    <td colSpan={8}>
                      <div className="empty-state">
                        {filtered ? "No school admins match these filters." : "No school admins yet. Add one to get started."}
                      </div>
                    </td>
                  </tr>
                ) : (
                  rows.map((admin) => (
                    <tr key={admin.id}>
                      <td>{schoolAdminDisplayName(admin)}</td>
                      <td>{admin.email}</td>
                      <td>{admin.mobile || "—"}</td>
                      <td>{admin.school_name}</td>
                      <td>{admin.role_label}</td>
                      <td>
                        <span className={`status-badge ${admin.status === 1 ? "paid" : "pending"}`}>
                          {schoolAdminStatusLabel(admin.status)}
                        </span>
                      </td>
                      <td>{formatDate(admin.created_at)}</td>
                      <td className="school-row-actions">
                        <Link className="link-btn" href={`/school-admins/${admin.id}`}>
                          View
                        </Link>
                        <Link className="link-btn" href={`/school-admins/${admin.id}/edit`}>
                          Edit
                        </Link>
                        <Link className="link-btn" href={`/school-admins/${admin.id}/roles`}>
                          Roles
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <div className="page-actions" style={{ margin: 16 }}>
            <button className="btn-pill btn-pill-green-soft" type="button" disabled={page <= 1 || loading} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span className="muted">
              Page {page} of {lastPage} · {total} admins
            </span>
            <button className="btn-pill btn-pill-green-soft" type="button" disabled={page >= lastPage || loading} onClick={() => setPage((p) => p + 1)}>
              Next
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function SchoolAdminsPage() {
  return (
    <Suspense fallback={<div className="skeleton" style={{ height: 120 }} />}>
      <SchoolAdminsPageInner />
    </Suspense>
  );
}
