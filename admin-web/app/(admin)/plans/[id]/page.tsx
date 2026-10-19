"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageHeading } from "@/components/dashboard/StatCard";
import { IconPackage } from "@/lib/icons";
import { api, apiErrorMessage } from "@/lib/api";
import { accessError, limitLabel, money, planStatusLabel, type Plan } from "@/lib/billing";

export default function PlanDetailPage() {
  const params = useParams<{ id: string }>();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [currency, setCurrency] = useState("INR");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [planResult, settings] = await Promise.all([
        api<Plan>(`/super-admin/plans/${params.id}`),
        api<{ settings?: { currency?: { value?: string | null } } }>("/super-admin/settings"),
      ]);
      if (cancelled) return;
      if (!planResult.ok) {
        setError(accessError(planResult.status, apiErrorMessage(planResult.data, "Unable to load this plan.")));
        return;
      }
      setPlan(planResult.data);
      const value = settings.ok ? settings.data.settings?.currency?.value : "";
      if (value) setCurrency(value);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  return (
    <div>
      <PageHeading title={plan?.name || "Subscription plan"} description="Plan details" icon={<IconPackage width={20} height={20} />} />
      <div className="page-actions">
        <Link className="btn-pill btn-pill-green-soft" href="/plans">
          All plans
        </Link>
        {plan ? (
          <Link className="btn-pill btn-pill-green" href={`/plans/${plan.id}/edit`}>
            Edit
          </Link>
        ) : null}
      </div>
      {error ? <div className="alert alert-danger">{error}</div> : null}
      {!plan && !error ? <p className="muted">Loading plan…</p> : null}
      {plan ? (
        <div className="panel-card resource-form">
          <dl className="detail-list">
            <div>
              <dt>Description</dt>
              <dd>{plan.description || "—"}</dd>
            </div>
            <div>
              <dt>Monthly price</dt>
              <dd>{money(plan.monthly_price, currency)}</dd>
            </div>
            <div>
              <dt>Yearly price</dt>
              <dd>{money(plan.yearly_price, currency)}</dd>
            </div>
            <div>
              <dt>Billing duration</dt>
              <dd>Monthly and yearly</dd>
            </div>
            <div>
              <dt>Student limit</dt>
              <dd>{limitLabel(plan.student_limit)}</dd>
            </div>
            <div>
              <dt>Staff / teacher limit</dt>
              <dd>{limitLabel(plan.staff_limit)}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>
                <span className={`status-badge ${plan.status === 1 ? "paid" : "pending"}`}>{planStatusLabel(plan.status)}</span>
              </dd>
            </div>
          </dl>
        </div>
      ) : null}
    </div>
  );
}
