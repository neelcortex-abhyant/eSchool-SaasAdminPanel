"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageHeading } from "@/components/dashboard/StatCard";
import { PlanForm, planToValues } from "@/components/billing/PlanForm";
import { IconPackage } from "@/lib/icons";
import { api, apiErrorMessage } from "@/lib/api";
import { accessError, type Plan } from "@/lib/billing";

export default function EditPlanPage() {
  const params = useParams<{ id: string }>();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const result = await api<Plan>(`/super-admin/plans/${params.id}`);
      if (cancelled) return;
      if (!result.ok) {
        setError(accessError(result.status, apiErrorMessage(result.data, "Unable to load this plan.")));
        return;
      }
      setPlan(result.data);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  return (
    <div>
      <PageHeading title="Edit subscription plan" description="Update the fields this plan allows" icon={<IconPackage width={20} height={20} />} />
      {error ? <div className="alert alert-danger">{error}</div> : null}
      {!plan && !error ? <p className="muted">Loading plan…</p> : null}
      {plan ? <PlanForm mode="edit" planId={plan.id} initial={planToValues(plan, "INR").values} /> : null}
    </div>
  );
}
