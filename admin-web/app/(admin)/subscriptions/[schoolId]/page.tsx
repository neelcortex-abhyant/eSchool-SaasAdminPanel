"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { PageHeading } from "@/components/dashboard/StatCard";
import { IconFees } from "@/lib/icons";
import { api, apiErrorMessage } from "@/lib/api";
import type { SchoolRecord } from "@/lib/school";
import {
  accessError,
  cycleLabel,
  formatDate,
  money,
  remainingDays,
  subscriptionStatusLabel,
  type Bill,
  type Plan,
  type Subscription,
} from "@/lib/billing";

function SubscriptionDetailPage() {
  const params = useParams<{ schoolId: string }>();
  const searchParams = useSearchParams();
  const [school, setSchool] = useState<SchoolRecord | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [bills, setBills] = useState<Bill[]>([]);
  const [currency, setCurrency] = useState("INR");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (searchParams.get("saved") === "assigned") setNotice("Subscription assigned.");
    if (searchParams.get("saved") === "renewed") setNotice("Subscription renewed.");
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      const [schoolResult, subsResult, settings] = await Promise.all([
        api<SchoolRecord>(`/super-admin/schools/${params.schoolId}`),
        api<{ items?: Subscription[] }>(`/super-admin/schools/${params.schoolId}/subscriptions?page=1&page_size=20`),
        api<{ settings?: { currency?: { value?: string | null } } }>("/super-admin/settings"),
      ]);
      if (cancelled) return;
      if (!schoolResult.ok) {
        setError(accessError(schoolResult.status, apiErrorMessage(schoolResult.data, "Unable to load this school.")));
        setLoading(false);
        return;
      }
      setSchool(schoolResult.data);
      const value = settings.ok ? settings.data.settings?.currency?.value : "";
      if (value) setCurrency(value);
      if (!subsResult.ok) {
        setError(accessError(subsResult.status, apiErrorMessage(subsResult.data, "Unable to load the subscription.")));
        setLoading(false);
        return;
      }
      const items = subsResult.data.items || [];
      const current = items.find((item) => item.status === 1) || items[0] || null;
      setSubscription(current);
      if (current) {
        const [planResult, billsResult] = await Promise.all([
          api<Plan>(`/super-admin/plans/${current.package_id}`),
          api<{ items?: Bill[] }>(`/super-admin/schools/${params.schoolId}/subscriptions/${current.id}/bills?page=1&page_size=10`),
        ]);
        if (!cancelled && planResult.ok) setPlan(planResult.data);
        if (!cancelled && billsResult.ok) setBills(billsResult.data.items || []);
      }
      if (!cancelled) setLoading(false);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [params.schoolId]);

  const price = subscription && plan ? (subscription.cycle === "yearly" ? plan.yearly_price : plan.monthly_price) : 0;
  const days = subscription ? remainingDays(subscription.end_date) : 0;

  return (
    <div>
      <PageHeading
        title={school?.name || "School subscription"}
        description="Current subscription for this school"
        icon={<IconFees width={20} height={20} />}
      />
      <div className="page-actions">
        <Link className="btn-pill btn-pill-green-soft" href="/subscriptions">
          All subscriptions
        </Link>
        <Link className="btn-pill btn-pill-green-soft" href={`/subscriptions/assign`}>
          Assign plan
        </Link>
        {subscription ? (
          <Link className="btn-pill btn-pill-green" href={`/subscriptions/${params.schoolId}/renew?subscription=${subscription.id}`}>
            Renew subscription
          </Link>
        ) : null}
      </div>
      {notice ? <div className="alert alert-success">{notice}</div> : null}
      {error ? <div className="alert alert-danger">{error}</div> : null}
      {loading ? <p className="muted">Loading subscription…</p> : null}
      {!loading && !error && !subscription ? (
        <div className="empty-state">This school has no subscription. Assign a plan to start one.</div>
      ) : null}
      {subscription ? (
        <div className="panel-card resource-form">
          <dl className="detail-list">
            <div>
              <dt>School</dt>
              <dd>{school?.name || "—"}</dd>
            </div>
            <div>
              <dt>Plan</dt>
              <dd>{plan?.name || `Plan ${subscription.package_id}`}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>
                <span className={`status-badge ${subscription.status === 1 ? "paid" : subscription.status === 3 ? "failed" : "pending"}`}>
                  {subscriptionStatusLabel(subscription.status)}
                </span>
              </dd>
            </div>
            <div>
              <dt>Price</dt>
              <dd>{money(price, currency)}</dd>
            </div>
            <div>
              <dt>Billing duration</dt>
              <dd>{cycleLabel(subscription.cycle)}</dd>
            </div>
            <div>
              <dt>Start date</dt>
              <dd>{formatDate(subscription.start_date)}</dd>
            </div>
            <div>
              <dt>Expiry date</dt>
              <dd>{formatDate(subscription.end_date)}</dd>
            </div>
            <div>
              <dt>Remaining</dt>
              <dd>{days >= 0 ? `${days} days` : `Expired ${Math.abs(days)} days ago`}</dd>
            </div>
          </dl>
          <h2 style={{ marginTop: 24, fontSize: 18 }}>Renewal details</h2>
          {bills.length === 0 ? (
            <p className="muted">No renewal bills are recorded for this subscription.</p>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Amount</th>
                    <th>Due</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {bills.map((bill) => (
                    <tr key={bill.id}>
                      <td>
                        {formatDate(bill.period_start)} – {formatDate(bill.period_end)}
                      </td>
                      <td>{money(bill.amount, currency)}</td>
                      <td>{formatDate(bill.due_date)}</td>
                      <td>{bill.status === 1 ? "Paid" : bill.status === 2 ? "Overdue" : bill.status === 3 ? "Cancelled" : "Pending"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

export default function SubscriptionDetailRoute() {
  return (
    <Suspense fallback={<p className="muted">Loading subscription…</p>}>
      <SubscriptionDetailPage />
    </Suspense>
  );
}
