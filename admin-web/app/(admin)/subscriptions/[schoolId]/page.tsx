"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { PaymentHistory } from "@/components/payments/PaymentHistory";
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

type Renewal = { id: number; plan_name: string; cycle: string; amount: number; period_start: string; period_end: string; created_at: string };

/** Status values: subscription 0 inactive, 1 active, 3 cancelled; bill 0 pending, 1 paid, 3 cancelled. */
type PendingChange = { kind: "subscription" | "bill"; billId?: number; status: number; title: string; body: string; done: string; danger?: boolean };

export default function SubscriptionDetailPage() {
  const params = useParams<{ schoolId: string }>();
  const [school, setSchool] = useState<SchoolRecord | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [bills, setBills] = useState<Bill[]>([]);
  const [currency, setCurrency] = useState("INR");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [renewals, setRenewals] = useState<Renewal[]>([]);
  const [version, setVersion] = useState(0);
  const [confirm, setConfirm] = useState<PendingChange | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Read once on mount: useSearchParams would force a Suspense fallback over the whole page.
    const saved = new URLSearchParams(window.location.search).get("saved");
    if (saved === "assigned") setNotice("Subscription assigned.");
    if (saved === "renewed") setNotice("Subscription renewed.");
  }, []);

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
        const [planResult, billsResult, renewalsResult] = await Promise.all([
          api<Plan>(`/super-admin/plans/${current.package_id}`),
          api<{ items?: Bill[] }>(`/super-admin/schools/${params.schoolId}/subscriptions/${current.id}/bills?page=1&page_size=10`),
          api<{ items?: Renewal[] }>(`/super-admin/schools/${params.schoolId}/subscriptions/${current.id}/renewals?page=1&page_size=20`),
        ]);
        if (!cancelled && planResult.ok) setPlan(planResult.data);
        if (!cancelled && billsResult.ok) setBills(billsResult.data.items || []);
        if (!cancelled && renewalsResult.ok) setRenewals(renewalsResult.data.items || []);
      }
      if (!cancelled) setLoading(false);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [params.schoolId, version]);

  /** Sends a status change to the subscription or one of its bills, after confirmation. */
  async function applyChange(change: PendingChange) {
    if (!subscription) return;
    setBusy(true);
    setError("");
    const base = `/super-admin/schools/${params.schoolId}/subscriptions/${subscription.id}`;
    const path = change.kind === "subscription" ? `${base}/status` : `${base}/bills/${change.billId}/status`;
    const result = await api(path, { method: "PATCH", body: JSON.stringify({ status: change.status }) });
    setBusy(false);
    setConfirm(null);
    if (!result.ok) {
      setError(accessError(result.status, apiErrorMessage(result.data, "Unable to change the status.")));
      return;
    }
    setNotice(change.done);
    setVersion((value) => value + 1);
  }

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
                </span>{" "}
                {subscription.status !== 1 ? (
                  <button className="link-btn" type="button" onClick={() => setConfirm({ kind: "subscription", status: 1, title: "Activate this subscription?", body: "The school gets the plan's features again.", done: "Subscription activated." })}>
                    Activate
                  </button>
                ) : (
                  <button className="link-btn" type="button" onClick={() => setConfirm({ kind: "subscription", status: 0, title: "Pause this subscription?", body: "The subscription is marked inactive until it's activated again.", done: "Subscription paused." })}>
                    Pause
                  </button>
                )}{" "}
                {subscription.status !== 3 ? (
                  <button className="link-btn danger" type="button" onClick={() => setConfirm({ kind: "subscription", status: 3, title: "Cancel this subscription?", body: "The school loses the plan when it's cancelled. This is recorded in the audit log.", done: "Subscription cancelled.", danger: true })}>
                    Cancel
                  </button>
                ) : null}
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
                    <th>
                      <span className="acad-sr">Actions</span>
                    </th>
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
                      <td>
                        {bill.status === 0 || bill.status === 2 ? (
                          <>
                            <button className="link-btn" type="button" onClick={() => setConfirm({ kind: "bill", billId: bill.id, status: 1, title: "Mark this bill as paid?", body: `Use this for a payment received outside the payment gateway (${money(bill.amount, currency)}).`, done: "Bill marked as paid." })}>
                              Mark paid
                            </button>{" "}
                            <button className="link-btn danger" type="button" onClick={() => setConfirm({ kind: "bill", billId: bill.id, status: 3, title: "Cancel this bill?", body: "The school won't be asked to pay it.", done: "Bill cancelled.", danger: true })}>
                              Cancel
                            </button>
                          </>
                        ) : bill.status === 3 ? (
                          <button className="link-btn" type="button" onClick={() => setConfirm({ kind: "bill", billId: bill.id, status: 0, title: "Reopen this bill?", body: "It goes back to pending.", done: "Bill reopened." })}>
                            Reopen
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
      {subscription && renewals.length ? (
        <div className="panel-card resource-form">
          <h2 style={{ fontSize: 18 }}>Renewal history</h2>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Renewed on</th>
                  <th>Plan</th>
                  <th>Period</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {renewals.map((row) => (
                  <tr key={row.id}>
                    <td>{formatDate(row.created_at)}</td>
                    <td>
                      {row.plan_name} · {cycleLabel(row.cycle)}
                    </td>
                    <td>
                      {formatDate(row.period_start)} – {formatDate(row.period_end)}
                    </td>
                    <td>{money(row.amount, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      {!loading && !error ? <PaymentHistory schoolId={Number(params.schoolId)} /> : null}
      {confirm ? (
        <ConfirmDialog title={confirm.title} body={confirm.body} confirmLabel="Confirm" tone={confirm.danger ? "danger" : "default"} pending={busy} onCancel={() => setConfirm(null)} onConfirm={() => void applyChange(confirm)} />
      ) : null}
    </div>
  );
}

