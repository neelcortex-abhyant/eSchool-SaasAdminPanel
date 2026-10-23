"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PageHeading } from "@/components/dashboard/StatCard";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { IconPackage } from "@/lib/icons";
import { api, apiErrorMessage } from "@/lib/api";
import { accessError, limitLabel, loadPlans, money, planStatusLabel, type Plan } from "@/lib/billing";

const PAGE_SIZE = 20;

export default function PlansPage() {
  const [rows, setRows] = useState<Plan[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [currency, setCurrency] = useState("INR");
  const [confirm, setConfirm] = useState<Plan | null>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);

  useEffect(() => {
    // Read once on mount: useSearchParams would force a Suspense fallback over the whole page.
    const saved = new URLSearchParams(window.location.search).get("saved");
    if (saved === "created") setNotice("Plan created.");
    if (saved === "updated") setNotice("Plan updated.");
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    void api<{ settings?: { currency?: { value?: string | null } } }>("/super-admin/settings").then((result) => {
      const value = result.ok ? result.data.settings?.currency?.value : "";
      if (value) setCurrency(value);
    });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const result = await loadPlans({ page, pageSize: PAGE_SIZE, name: search, status });
    if (!result.ok) {
      setError(accessError(result.status, apiErrorMessage(result.data, "Unable to load plans.")));
      setRows([]);
      setTotal(0);
    } else {
      setRows(result.data.items || []);
      setTotal(result.data.total || 0);
    }
    setLoading(false);
  }, [page, search, status]);

  useEffect(() => {
    void load();
  }, [load]);

  async function changeStatus() {
    if (!confirm) return;
    const next = confirm.status === 1 ? 0 : 1;
    setPendingId(confirm.id);
    setError("");
    const result = await api(`/super-admin/plans/${confirm.id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: next }),
    });
    setPendingId(null);
    setConfirm(null);
    if (!result.ok) {
      setError(accessError(result.status, apiErrorMessage(result.data, "Unable to update this plan.")));
      return;
    }
    setNotice(next === 1 ? "Plan activated." : "Plan deactivated.");
    await load();
  }

  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const filtered = Boolean(search || status);

  return (
    <div>
      <PageHeading title="Subscription plans" description="Plans schools can be assigned" icon={<IconPackage width={20} height={20} />} />
      <div className="page-actions">
        <Link className="btn-pill btn-pill-green" href="/plans/new">
          Create plan
        </Link>
      </div>
      <div className="school-filters">
        <input
          type="search"
          aria-label="Search plans by name"
          placeholder="Search by plan name"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
        />
        <select
          aria-label="Filter by plan status"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          <option value="1">Active</option>
          <option value="0">Inactive</option>
        </select>
        <button
          className="btn-pill btn-pill-green-soft"
          type="button"
          onClick={() => {
            setSearchInput("");
            setSearch("");
            setStatus("");
            setPage(1);
          }}
        >
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
                  <th>Plan</th>
                  <th>Description</th>
                  <th>Price</th>
                  <th>Billing</th>
                  <th>Students</th>
                  <th>Staff</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={8}>
                      <div className="empty-state">
                        {filtered ? "No plans match these filters." : "No subscription plans yet. Create a plan to see it here."}
                      </div>
                    </td>
                  </tr>
                ) : (
                  rows.map((plan) => (
                    <tr key={plan.id}>
                      <td>{plan.name || "—"}</td>
                      <td>{plan.description || "—"}</td>
                      <td>
                        {money(plan.monthly_price, currency)} / mo
                        <br />
                        {money(plan.yearly_price, currency)} / yr
                      </td>
                      <td>Monthly and yearly</td>
                      <td>{limitLabel(plan.student_limit)}</td>
                      <td>{limitLabel(plan.staff_limit)}</td>
                      <td>
                        <span className={`status-badge ${plan.status === 1 ? "paid" : "pending"}`}>{planStatusLabel(plan.status)}</span>
                      </td>
                      <td className="school-row-actions">
                        <Link className="link-btn" href={`/plans/${plan.id}`}>
                          View
                        </Link>
                        <Link className="link-btn" href={`/plans/${plan.id}/edit`}>
                          Edit
                        </Link>
                        <button type="button" className="link-btn" disabled={pendingId === plan.id} onClick={() => setConfirm(plan)}>
                          {plan.status === 1 ? "Deactivate" : "Activate"}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <div className="page-actions" style={{ margin: 16 }}>
            <button className="btn-pill btn-pill-green-soft" type="button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>
              Previous
            </button>
            <span className="muted">
              Page {page} of {lastPage} · {total} plans
            </span>
            <button className="btn-pill btn-pill-green-soft" type="button" disabled={page >= lastPage} onClick={() => setPage((current) => current + 1)}>
              Next
            </button>
          </div>
        </div>
      ) : null}
      {confirm ? (
        <ConfirmDialog
          title={confirm.status === 1 ? "Deactivate plan" : "Activate plan"}
          body={
            confirm.status === 1
              ? `Deactivate ${confirm.name || "this plan"}? Schools will not be able to take new assignments on it.`
              : `Activate ${confirm.name || "this plan"}? It can be assigned to schools.`
          }
          confirmLabel={confirm.status === 1 ? "Deactivate" : "Activate"}
          pending={pendingId !== null}
          onConfirm={() => void changeStatus()}
          onCancel={() => setConfirm(null)}
        />
      ) : null}
    </div>
  );
}

