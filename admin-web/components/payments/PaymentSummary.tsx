"use client";

import { useEffect, useState } from "react";
import { StatCard, StatCardSkeleton } from "@/components/dashboard/StatCard";
import { apiErrorMessage } from "@/lib/api";
import { money } from "@/lib/billing";
import { loadPaymentSummary, type PaymentSummary } from "@/lib/payments";

export function PaymentSummaryCards() {
  const [summary, setSummary] = useState<PaymentSummary | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const result = await loadPaymentSummary();
      if (cancelled) return;
      if (!result.ok) {
        setError(result.status === 401 ? "Sign in again to view payment totals." : result.status === 403 ? "This account cannot view payment totals." : apiErrorMessage(result.data, "Unable to load payment totals."));
      } else {
        setSummary(result.data);
      }
      setLoading(false);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <section className="stat-grid" aria-label="Payment summary">
        {Array.from({ length: 4 }).map((_, index) => (
          <StatCardSkeleton key={index} />
        ))}
      </section>
    );
  }

  if (error) return <div className="alert alert-danger">{error}</div>;
  if (!summary) return null;

  const currency = summary.currency || "INR";
  return (
    <section>
      {summary.source === "sample" ? (
        <div className="alert alert-info">Sample totals. Payment transactions are not stored, so these figures are not collected revenue.</div>
      ) : (
        <p className="muted">Totals cover every recorded payment, not the current page.</p>
      )}
      <section className="stat-grid" aria-label="Payment summary">
        <StatCard
          data={{
            id: "pay-amount",
            title: "Successful amount",
            value: money(summary.successful_amount, currency),
            meta: summary.source === "sample" ? "Sample" : "All successful payments",
            tone: "green",
            icon: "payments",
          }}
        />
        <StatCard
          data={{
            id: "pay-success",
            title: "Successful payments",
            value: String(summary.successful_count),
            meta: summary.source === "sample" ? "Sample" : "All successful payments",
            tone: "teal",
            icon: "payments",
          }}
        />
        <StatCard
          data={{
            id: "pay-pending",
            title: "Pending payments",
            value: String(summary.pending_count),
            meta: summary.source === "sample" ? "Sample" : "All pending payments",
            tone: "orange",
            icon: "payments",
          }}
        />
        <StatCard
          data={{
            id: "pay-failed",
            title: "Failed payments",
            value: String(summary.failed_count),
            meta: summary.source === "sample" ? "Sample" : "All failed payments",
            tone: "rose",
            icon: "payments",
          }}
        />
      </section>
    </section>
  );
}
