"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { PageHeading } from "@/components/dashboard/StatCard";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { IconFees } from "@/lib/icons";
import { api, apiErrorMessage } from "@/lib/api";
import { accessError, cycleLabel, formatDate, money, renewedPeriod, subscriptionStatusLabel, type Plan, type Subscription } from "@/lib/billing";

type SubscriptionPreview = {
  plan_name: string | null;
  package_id: number;
  status: number;
  cycle: string;
  price: number;
  end_date: string;
  proposed_end_date: string | null;
  can_renew: boolean;
  reason: string | null;
};

function RenewPage() {
  const params = useParams<{ schoolId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const subscriptionId = searchParams.get("subscription");
  const [preview, setPreview] = useState<SubscriptionPreview | null>(null);
  const [currency, setCurrency] = useState("INR");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);

  async function load() {
    if (!subscriptionId) {
      setError("Choose a subscription to renew.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    const [subscription, settings] = await Promise.all([
      api<Subscription>(`/super-admin/schools/${params.schoolId}/subscriptions/${subscriptionId}`),
      api<{ settings?: { currency?: { value?: string | null } } }>("/super-admin/settings"),
    ]);
    if (!subscription.ok) {
      setError(accessError(subscription.status, apiErrorMessage(subscription.data, "Unable to load the renewal.")));
      setPreview(null);
    } else {
      const current = subscription.data;
      const planResult = await api<Plan>(`/super-admin/plans/${current.package_id}`);
      const plan = planResult.ok ? planResult.data : null;
      const cycle = current.cycle === "yearly" ? "yearly" : "monthly";
      const active = current.status === 1;
      const period = active ? renewedPeriod(current.end_date, cycle) : null;
      setPreview({
        plan_name: plan?.name || null,
        package_id: current.package_id,
        status: current.status,
        cycle: current.cycle,
        price: plan ? (cycle === "yearly" ? plan.yearly_price : plan.monthly_price) : 0,
        end_date: current.end_date,
        proposed_end_date: period?.end || null,
        can_renew: active,
        reason: active ? null : "Only an active subscription can be renewed.",
      });
    }
    const value = settings.ok ? settings.data.settings?.currency?.value : "";
    if (value) setCurrency(value);
    setLoading(false);
  }

  useEffect(() => {
    void load();
  }, [params.schoolId, subscriptionId]);

  async function renew() {
    if (!subscriptionId) return;
    setSaving(true);
    setError("");
    try {
      const result = await api(`/super-admin/schools/${params.schoolId}/subscriptions/${subscriptionId}/renew`, { method: "POST" });
      if (!result.ok) {
        setConfirming(false);
        setError(accessError(result.status, apiErrorMessage(result.data, "Unable to renew this subscription.")));
        await load();
        return;
      }
      router.push(`/subscriptions/${params.schoolId}?saved=renewed`);
      router.refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Network error.";
      setError(`Network error contacting the subscription API. (${message})`);
      setConfirming(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <PageHeading title="Renew subscription" description="Review the next expiry before confirming" icon={<IconFees width={20} height={20} />} />
      <div className="page-actions">
        <Link className="btn-pill btn-pill-green-soft" href={`/subscriptions/${params.schoolId}`}>
          Back to subscription
        </Link>
      </div>
      {error ? <div className="alert alert-danger">{error}</div> : null}
      {loading ? <p className="muted">Loading renewal…</p> : null}
      {preview ? (
        <div className="panel-card resource-form">
          <dl className="detail-list">
            <div>
              <dt>Plan</dt>
              <dd>{preview.plan_name || `Plan ${preview.package_id}`}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{subscriptionStatusLabel(preview.status)}</dd>
            </div>
            <div>
              <dt>Billing duration</dt>
              <dd>{cycleLabel(preview.cycle)}</dd>
            </div>
            <div>
              <dt>Price</dt>
              <dd>{money(preview.price, currency)}</dd>
            </div>
            <div>
              <dt>Current expiry</dt>
              <dd>{formatDate(preview.end_date)}</dd>
            </div>
            <div>
              <dt>Proposed expiry</dt>
              <dd>{preview.proposed_end_date ? formatDate(preview.proposed_end_date) : "—"}</dd>
            </div>
          </dl>
          {preview.reason ? <div className="alert alert-info">{preview.reason}</div> : null}
          <div className="page-actions">
            <button className="btn-pill btn-pill-green" type="button" disabled={!preview.can_renew} onClick={() => setConfirming(true)}>
              Renew subscription
            </button>
          </div>
        </div>
      ) : null}
      {confirming && preview?.proposed_end_date ? (
        <ConfirmDialog
          title="Confirm renewal"
          body={`Renew ${preview.plan_name || "this plan"} for ${money(preview.price, currency)}? The new expiry date will be ${formatDate(preview.proposed_end_date)}.`}
          confirmLabel="Renew"
          pending={saving}
          onConfirm={() => void renew()}
          onCancel={() => setConfirming(false)}
        />
      ) : null}
    </div>
  );
}

export default function RenewRoute() {
  return (
    <Suspense fallback={<p className="muted">Loading renewal…</p>}>
      <RenewPage />
    </Suspense>
  );
}
