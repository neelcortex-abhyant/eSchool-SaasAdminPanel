"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PageHeading } from "@/components/dashboard/StatCard";
import { IconFees } from "@/lib/icons";
import { api, apiErrorMessage } from "@/lib/api";
import {
  accessError,
  cycleLabel,
  formatDate,
  loadPlans,
  loadSubscriptionCatalog,
  money,
  subscriptionStatusLabel,
  type Plan,
  type Subscription,
} from "@/lib/billing";

const PAGE_SIZE = 20;

export default function SubscriptionsPage() {
  const [rows, setRows] = useState<Subscription[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [planId, setPlanId] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState<"end_date" | "-end_date">("-end_date");
  const [currency, setCurrency] = useState("INR");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    void loadPlans({ page: 1, pageSize: 100 }).then((result) => {
      if (result.ok) setPlans(result.data.items || []);
    });
    void api<{ settings?: { currency?: { value?: string | null } } }>("/super-admin/settings").then((result) => {
      const value = result.ok ? result.data.settings?.currency?.value : "";
      if (value) setCurrency(value);
    });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const result = await loadSubscriptionCatalog({
      page,
      pageSize: PAGE_SIZE,
      q: search,
      packageId: planId,
      status,
      sort,
    });
    if (!result.ok) {
      setError(accessError(result.status, apiErrorMessage(result.data, "Unable to load subscriptions.")));
      setRows([]);
      setTotal(0);
    } else {
      setRows(result.data.items || []);
      setTotal(result.data.total || 0);
    }
    setLoading(false);
  }, [page, search, planId, status, sort]);

  useEffect(() => {
    void load();
  }, [load]);

  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const filtered = Boolean(search || planId || status);

  return (
    <div>
      <PageHeading title="School subscriptions" description="Plans assigned to schools" icon={<IconFees width={20} height={20} />} />
      <div className="page-actions">
        <Link className="btn-pill btn-pill-green" href="/subscriptions/assign">
          Assign plan
        </Link>
      </div>
      <div className="school-filters">
        <input
          type="search"
          aria-label="Search by school name"
          placeholder="Search by school name"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
        />
        <select
          aria-label="Filter by plan"
          value={planId}
          onChange={(event) => {
            setPlanId(event.target.value);
            setPage(1);
          }}
        >
          <option value="">All plans</option>
          {plans.map((plan) => (
            <option key={plan.id} value={plan.id}>
              {plan.name || `Plan ${plan.id}`}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter by subscription status"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          <option value="1">Active</option>
          <option value="0">Inactive</option>
          <option value="2">Expired</option>
          <option value="3">Cancelled</option>
        </select>
        <button
          className="btn-pill btn-pill-green-soft"
          type="button"
          onClick={() => {
            setSearchInput("");
            setSearch("");
            setPlanId("");
            setStatus("");
            setSort("-end_date");
            setPage(1);
          }}
        >
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
                  <th>School</th>
                  <th>Plan</th>
                  <th>Price</th>
                  <th>Start</th>
                  <th>
                    <button
                      type="button"
                      className="sort-btn"
                      onClick={() => {
                        setSort((current) => (current === "-end_date" ? "end_date" : "-end_date"));
                        setPage(1);
                      }}
                    >
                      Expiry {sort === "end_date" ? "↑" : "↓"}
                    </button>
                  </th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={7}>
                      <div className="empty-state">
                        {filtered ? "No subscriptions match these filters." : "No school subscriptions yet. Assign a plan to a school."}
                      </div>
                    </td>
                  </tr>
                ) : (
                  rows.map((row) => (
                    <tr key={row.id}>
                      <td>{row.school_name || `School ${row.school_id}`}</td>
                      <td>{row.plan_name || `Plan ${row.package_id}`}</td>
                      <td>
                        {row.agreed_price == null ? "—" : money(row.agreed_price, currency)}
                        <br />
                        <span className="muted">{cycleLabel(row.cycle)}</span>
                      </td>
                      <td>{formatDate(row.start_date)}</td>
                      <td>{formatDate(row.end_date)}</td>
                      <td>
                        <span className={`status-badge ${row.status === 1 ? "paid" : row.status === 3 ? "failed" : "pending"}`}>
                          {subscriptionStatusLabel(row.status)}
                        </span>
                      </td>
                      <td className="school-row-actions">
                        <Link className="link-btn" href={`/subscriptions/${row.school_id}`}>
                          View
                        </Link>
                        <Link className="link-btn" href={`/subscriptions/${row.school_id}/renew?subscription=${row.id}`}>
                          Renew
                        </Link>
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
              Page {page} of {lastPage} · {total} subscriptions
            </span>
            <button className="btn-pill btn-pill-green-soft" type="button" disabled={page >= lastPage} onClick={() => setPage((current) => current + 1)}>
              Next
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
