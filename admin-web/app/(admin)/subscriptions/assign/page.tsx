"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeading } from "@/components/dashboard/StatCard";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { IconFees } from "@/lib/icons";
import { api, apiErrorMessage } from "@/lib/api";
import { loadSchools, type SchoolRecord } from "@/lib/school";
import { accessError, addCycle, cycleLabel, formatDate, loadPlans, money, todayIso, type Plan } from "@/lib/billing";

export default function AssignSubscriptionPage() {
  const router = useRouter();
  const [schools, setSchools] = useState<SchoolRecord[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [schoolId, setSchoolId] = useState("");
  const [planId, setPlanId] = useState("");
  const [cycle, setCycle] = useState<"monthly" | "yearly">("monthly");
  const [startDate, setStartDate] = useState(todayIso());
  const [currency, setCurrency] = useState("INR");
  const [error, setError] = useState("");
  const [schoolQuery, setSchoolQuery] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadSchools({ page: 1, pageSize: 20, q: schoolQuery, status: "1" }).then((result) => {
        if (result.ok) setSchools(result.data.items || []);
      });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [schoolQuery]);

  useEffect(() => {
    void loadPlans({ page: 1, pageSize: 100, status: "1" }).then((result) => {
      if (result.ok) setPlans(result.data.items || []);
    });
    void api<{ settings?: { currency?: { value?: string | null } } }>("/super-admin/settings").then((result) => {
      const value = result.ok ? result.data.settings?.currency?.value : "";
      if (value) setCurrency(value);
    });
  }, []);

  const plan = plans.find((item) => String(item.id) === planId);
  const school = schools.find((item) => String(item.id) === schoolId);
  const price = plan ? (cycle === "yearly" ? plan.yearly_price : plan.monthly_price) : 0;
  const endDate = startDate ? addCycle(startDate, cycle) : "";

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!schoolId || !planId || !startDate) {
      setError("Select a school, an active plan, and a start date.");
      return;
    }
    setError("");
    setConfirming(true);
  }

  async function assign() {
    setSaving(true);
    setError("");
    try {
      const result = await api<{ id: number }>(`/super-admin/schools/${schoolId}/subscriptions`, {
        method: "POST",
        body: JSON.stringify({
          package_id: Number(planId),
          start_date: startDate,
          end_date: endDate,
          cycle,
          auto_renew: 1,
          status: 1,
        }),
      });
      if (!result.ok) {
        setConfirming(false);
        setError(accessError(result.status, apiErrorMessage(result.data, "Unable to assign this subscription.")));
        return;
      }
      router.push(`/subscriptions/${schoolId}?saved=assigned`);
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
      <PageHeading title="Assign subscription" description="Choose a school and an active plan" icon={<IconFees width={20} height={20} />} />
      {error ? <div className="alert alert-danger">{error}</div> : null}
      <form className="panel-card resource-form" onSubmit={onSubmit}>
        <div className="resource-fields">
          <label className="form-field">
            Find school
            <input value={schoolQuery} placeholder="Search by name or code" onChange={(event) => setSchoolQuery(event.target.value)} />
          </label>
          <label className="form-field">
            School
            <select value={schoolId} onChange={(event) => setSchoolId(event.target.value)} required>
              <option value="">Select a school</option>
              {schools.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name || `School ${item.id}`}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            Plan
            <select value={planId} onChange={(event) => setPlanId(event.target.value)} required>
              <option value="">Select an active plan</option>
              {plans.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name || `Plan ${item.id}`}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            Billing duration
            <select value={cycle} onChange={(event) => setCycle(event.target.value as "monthly" | "yearly")}>
              <option value="monthly">Monthly</option>
              <option value="yearly">Yearly</option>
            </select>
          </label>
          <label className="form-field">
            Price
            <input value={plan ? money(price, currency) : "—"} readOnly />
          </label>
          <label className="form-field">
            Start date
            <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} required />
          </label>
          <label className="form-field">
            Proposed expiry
            <input value={endDate ? formatDate(endDate) : "—"} readOnly />
          </label>
        </div>
        <div className="page-actions">
          <button className="btn-pill btn-pill-green" type="submit">
            Review assignment
          </button>
          <button className="btn-pill btn-pill-green-soft" type="button" onClick={() => router.push("/subscriptions")}>
            Cancel
          </button>
        </div>
      </form>
      {confirming ? (
        <ConfirmDialog
          title="Assign subscription"
          body={`Assign ${plan?.name || "this plan"} (${cycleLabel(cycle)}, ${money(price, currency)}) to ${school?.name || "this school"} from ${formatDate(startDate)} until ${formatDate(endDate)}? Any other active subscription for this school will be cancelled.`}
          confirmLabel="Assign"
          pending={saving}
          onConfirm={() => void assign()}
          onCancel={() => setConfirming(false)}
        />
      ) : null}
    </div>
  );
}
