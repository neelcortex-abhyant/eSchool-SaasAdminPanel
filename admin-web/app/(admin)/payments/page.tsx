"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PageHeading } from "@/components/dashboard/StatCard";
import { PaymentSummaryCards } from "@/components/payments/PaymentSummary";
import { StatusBadge } from "@/components/payments/PaymentHistory";
import { IconFees } from "@/lib/icons";
import { apiErrorMessage } from "@/lib/api";
import { formatDate, money } from "@/lib/billing";
import {
  downloadInvoice,
  loadPayments,
  sampleGateways,
  type PaymentStatus,
  type PaymentTransaction,
} from "@/lib/payments";

const PAGE_SIZE = 8;

export default function PaymentsPage() {
  const [rows, setRows] = useState<PaymentTransaction[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [source, setSource] = useState<"api" | "sample">("api");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | PaymentStatus>("");
  const [gateway, setGateway] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [sort, setSort] = useState<"created_at" | "-created_at">("-created_at");
  const [downloading, setDownloading] = useState("");
  const [gatewayOptions, setGatewayOptions] = useState<string[]>([]);

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
    const result = await loadPayments({ page, pageSize: PAGE_SIZE, q: search, status, gateway, from, to, sort });
    if (!result.ok) {
      setRows([]);
      setTotal(0);
      setError(result.status === 401 ? "Sign in again to view payments." : result.status === 403 ? "This account cannot view payments." : apiErrorMessage(result.data, "Unable to load payments."));
    } else {
      const items = result.data.items || [];
      setRows(items);
      setTotal(result.data.total || 0);
      setSource(result.data.source);
      setGatewayOptions((current) => {
        if (result.data.source === "sample") return sampleGateways();
        const names = new Set(current);
        items.forEach((item) => names.add(item.gateway));
        return Array.from(names).sort();
      });
    }
    setLoading(false);
  }, [page, search, status, gateway, from, to, sort]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onDownload(payment: PaymentTransaction) {
    setDownloading(payment.id);
    setNotice("");
    setError("");
    const result = await downloadInvoice(payment);
    setDownloading("");
    if (!result.ok) setError(result.message);
    else setNotice(payment.invoice ? `Invoice ${payment.invoice.number} download started.` : "Invoice download started.");
  }

  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const filtered = Boolean(search || status || gateway || from || to);

  return (
    <div>
      <PageHeading title="Payment transactions" description="Subscription payments recorded for schools" icon={<IconFees width={20} height={20} />} />
      <PaymentSummaryCards />
      {source === "sample" && !loading ? (
        <div className="alert alert-info">Sample records. Payment transactions are not stored yet, so these rows are not collected payments.</div>
      ) : null}
      <div className="school-filters">
        <input type="search" aria-label="Search by transaction or school" placeholder="Transaction ID or school" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} />
        <select
          aria-label="Filter by payment status"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value as "" | PaymentStatus);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          <option value="successful">Successful</option>
          <option value="pending">Pending</option>
          <option value="failed">Failed</option>
          <option value="refunded">Refunded</option>
        </select>
        <select
          aria-label="Filter by payment gateway"
          value={gateway}
          onChange={(event) => {
            setGateway(event.target.value);
            setPage(1);
          }}
        >
          <option value="">All gateways</option>
          {gatewayOptions.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <input aria-label="Payment from date" type="date" value={from} onChange={(event) => { setFrom(event.target.value); setPage(1); }} />
        <input aria-label="Payment to date" type="date" value={to} onChange={(event) => { setTo(event.target.value); setPage(1); }} />
        <button
          className="btn-pill btn-pill-green-soft"
          type="button"
          onClick={() => {
            setSearchInput("");
            setSearch("");
            setStatus("");
            setGateway("");
            setFrom("");
            setTo("");
            setSort("-created_at");
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
                  <th>Transaction</th>
                  <th>School</th>
                  <th>Plan</th>
                  <th>Amount</th>
                  <th>Gateway</th>
                  <th>
                    <button type="button" className="sort-btn" onClick={() => { setSort((current) => (current === "-created_at" ? "created_at" : "-created_at")); setPage(1); }}>
                      Date {sort === "created_at" ? "↑" : "↓"}
                    </button>
                  </th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={8}>
                      <div className="empty-state">{filtered ? "No payments match these filters." : "No payment transactions yet."}</div>
                    </td>
                  </tr>
                ) : (
                  rows.map((payment) => (
                    <tr key={payment.id}>
                      <td className="mono">{payment.id}</td>
                      <td>{payment.school_name}</td>
                      <td>{payment.plan_name}</td>
                      <td>{money(payment.amount, payment.currency)}</td>
                      <td>{payment.gateway}</td>
                      <td>{formatDate(payment.created_at)}</td>
                      <td>
                        <StatusBadge status={payment.status} />
                      </td>
                      <td className="school-row-actions">
                        <Link className="link-btn" href={`/payments/${payment.id}`}>
                          View
                        </Link>
                        {payment.status === "successful" ? (
                          <button className="link-btn" type="button" disabled={downloading === payment.id} onClick={() => void onDownload(payment)}>
                            {downloading === payment.id ? "Downloading…" : "Invoice"}
                          </button>
                        ) : null}
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
              Page {page} of {lastPage} · {total} payments
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
