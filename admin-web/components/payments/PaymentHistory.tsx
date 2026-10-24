"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiErrorMessage } from "@/lib/api";
import { formatDate, money } from "@/lib/billing";
import { downloadInvoice, loadSchoolPayments, paymentDate, paymentStatusLabel, type PaymentTransaction } from "@/lib/payments";

const PAGE_SIZE = 10;

export function PaymentHistory({ schoolId }: { schoolId: number }) {
  const [rows, setRows] = useState<PaymentTransaction[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [downloading, setDownloading] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const result = await loadSchoolPayments(schoolId, { page, pageSize: PAGE_SIZE, sort: "-created_at" });
    if (!result.ok) {
      setRows([]);
      setTotal(0);
      setError(result.status === 401 ? "Sign in again to view payments." : result.status === 403 ? "This account cannot view this school's payments." : apiErrorMessage(result.data, "Unable to load payment history."));
    } else {
      setRows(result.data.items || []);
      setTotal(result.data.total || 0);
    }
    setLoading(false);
  }, [schoolId, page]);

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
    else setNotice("Invoice download started.");
  }

  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <article className="panel-card">
      <div className="panel-card-header">
        <h2>Payment history</h2>
      </div>
      {notice ? <div className="alert alert-success">{notice}</div> : null}
      {error ? <div className="alert alert-danger">{error}</div> : null}
      {loading ? <p className="muted">Loading payments…</p> : null}
      {!loading && !error && rows.length === 0 ? <div className="empty-state">No payments are recorded for this school.</div> : null}
      {!loading && rows.length > 0 ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Transaction</th>
                <th>Plan</th>
                <th>Amount</th>
                <th>Date</th>
                <th>Status</th>
                <th>Invoice</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((payment) => (
                <tr key={payment.id}>
                  <td>
                    <Link className="link-btn" href={`/payments/${payment.id}`}>
                      {payment.id}
                    </Link>
                  </td>
                  <td>{payment.plan_name}</td>
                  <td>{money(payment.amount, payment.currency)}</td>
                  <td>{formatDate(paymentDate(payment))}</td>
                  <td>
                    <StatusBadge status={payment.status} />
                  </td>
                  <td>
                    {payment.invoice && payment.status === "successful" ? (
                      <button className="link-btn" type="button" disabled={downloading === payment.id} onClick={() => void onDownload(payment)}>
                        {downloading === payment.id ? "Downloading…" : "Download"}
                      </button>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {total > PAGE_SIZE ? (
        <div className="page-actions" style={{ margin: 16 }}>
          <button className="btn-pill btn-pill-green-soft" type="button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>
            Previous
          </button>
          <span className="muted">
            Page {page} of {lastPage}
          </span>
          <button className="btn-pill btn-pill-green-soft" type="button" disabled={page >= lastPage} onClick={() => setPage((current) => current + 1)}>
            Next
          </button>
        </div>
      ) : null}
    </article>
  );
}

export function StatusBadge({ status }: { status: PaymentTransaction["status"] }) {
  const tone = status === "successful" ? "paid" : status === "failed" ? "failed" : status === "refunded" ? "refunded" : "pending";
  return <span className={`status-badge ${tone}`}>{paymentStatusLabel(status)}</span>;
}
