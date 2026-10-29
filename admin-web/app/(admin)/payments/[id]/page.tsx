"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageHeading } from "@/components/dashboard/StatCard";
import { StatusBadge } from "@/components/payments/PaymentHistory";
import { IconFees } from "@/lib/icons";
import { apiErrorMessage } from "@/lib/api";
import { formatDate, money } from "@/lib/billing";
import { downloadInvoice, loadPayment, type PaymentTransaction } from "@/lib/payments";

export default function PaymentDetailPage() {
  const params = useParams<{ id: string }>();
  const [payment, setPayment] = useState<(PaymentTransaction & { source?: "api" | "sample" }) | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const result = await loadPayment(params.id);
      if (cancelled) return;
      if (result.status === 404) {
        setMissing(true);
      } else if (!result.ok) {
        setError(result.status === 401 ? "Sign in again to view this payment." : result.status === 403 ? "This account cannot view this payment." : apiErrorMessage(result.data, "Unable to load this payment."));
      } else {
        setPayment(result.data);
      }
      setLoading(false);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  async function onDownload() {
    if (!payment) return;
    setDownloading(true);
    setNotice("");
    setError("");
    const result = await downloadInvoice(payment);
    setDownloading(false);
    if (!result.ok) setError(result.message);
    else setNotice("Invoice download started.");
  }

  return (
    <div>
      <PageHeading title={payment ? (/^\d+$/.test(payment.id) ? `Payment #${payment.id}` : payment.id) : "Payment"} description="Transaction details" icon={<IconFees width={20} height={20} />} />
      <div className="page-actions">
        <Link className="btn-pill btn-pill-green-soft" href="/payments">
          All payments
        </Link>
      </div>
      {payment?.source === "sample" ? <div className="alert alert-info">Sample record. This payment is not stored and no card or gateway secret is included.</div> : null}
      {notice ? <div className="alert alert-success">{notice}</div> : null}
      {error ? <div className="alert alert-danger">{error}</div> : null}
      {loading ? <p className="muted">Loading payment…</p> : null}
      {missing ? <div className="empty-state">This transaction does not exist.</div> : null}
      {payment ? (
        <div className="panel-card resource-form">
          <dl className="detail-list">
            <div>
              <dt>Transaction ID</dt>
              <dd className="mono">{payment.id}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>
                <StatusBadge status={payment.status} />
              </dd>
            </div>
            <div>
              <dt>School</dt>
              <dd>
                {payment.school_name}
                {payment.school_code ? ` · ${payment.school_code}` : ""}
              </dd>
            </div>
            <div>
              <dt>Plan</dt>
              <dd>{payment.plan_name}</dd>
            </div>
            <div>
              <dt>Amount</dt>
              <dd>{money(payment.amount, payment.currency)}</dd>
            </div>
            <div>
              <dt>Gateway</dt>
              <dd>{payment.gateway}</dd>
            </div>
            <div>
              <dt>Gateway reference</dt>
              <dd className="mono">{payment.gateway_reference || "—"}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatDate(payment.created_at)}</dd>
            </div>
            <div>
              <dt>Completed</dt>
              <dd>{payment.paid_at ? formatDate(payment.paid_at) : "—"}</dd>
            </div>
            <div>
              <dt>Invoice</dt>
              <dd>{payment.invoice ? `${payment.invoice.number} · ${formatDate(payment.invoice.date)}` : "No invoice has been generated."}</dd>
            </div>
          </dl>
          {payment.status === "successful" ? (
            <div className="page-actions">
              <button className="btn-pill btn-pill-green" type="button" disabled={downloading || !payment.invoice} onClick={() => void onDownload()}>
                {downloading ? "Downloading…" : "Download invoice"}
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
