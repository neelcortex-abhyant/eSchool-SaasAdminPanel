"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, apiErrorMessage } from "@/lib/api";
import { accessError, type Plan } from "@/lib/billing";

type Values = {
  name: string;
  description: string;
  monthly_price: string;
  yearly_price: string;
  student_limit: string;
  staff_limit: string;
  status: "0" | "1";
};

type Errors = Partial<Record<keyof Values, string>>;

export function planToValues(plan: Plan, currency: string): { values: Values; currency: string } {
  return {
    currency,
    values: {
      name: plan.name || "",
      description: plan.description || "",
      monthly_price: String(plan.monthly_price ?? 0),
      yearly_price: String(plan.yearly_price ?? 0),
      student_limit: plan.student_limit == null ? "" : String(plan.student_limit),
      staff_limit: plan.staff_limit == null ? "" : String(plan.staff_limit),
      status: plan.status === 1 ? "1" : "0",
    },
  };
}

export function PlanForm({ mode, planId, initial }: { mode: "create" | "edit"; planId?: number; initial?: Values }) {
  const router = useRouter();
  const [values, setValues] = useState<Values>(
    initial || {
      name: "",
      description: "",
      monthly_price: "",
      yearly_price: "",
      student_limit: "",
      staff_limit: "",
      status: "1",
    },
  );
  const [currency, setCurrency] = useState("INR");
  const [fieldErrors, setFieldErrors] = useState<Errors>({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadCurrency() {
      const result = await api<{ settings?: { currency?: { value?: string | null } } }>("/super-admin/settings");
      const value = result.ok ? result.data.settings?.currency?.value : "";
      if (!cancelled && value) setCurrency(value);
    }
    void loadCurrency();
    return () => {
      cancelled = true;
    };
  }, []);

  function setField(key: keyof Values, value: string) {
    setValues((current) => ({ ...current, [key]: value }));
    setFieldErrors((current) => ({ ...current, [key]: undefined }));
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const errors = validate(values);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      setError("Fix the highlighted fields.");
      return;
    }
    setSaving(true);
    setError("");
    const body = {
      name: values.name.trim(),
      description: values.description.trim(),
      monthly_price: Number(values.monthly_price),
      yearly_price: Number(values.yearly_price),
      student_limit: values.student_limit.trim() === "" ? null : Number(values.student_limit),
      staff_limit: values.staff_limit.trim() === "" ? null : Number(values.staff_limit),
    };
    try {
      const result = await api<Plan>(mode === "create" ? "/super-admin/plans" : `/super-admin/plans/${planId}`, {
        method: mode === "create" ? "POST" : "PATCH",
        body: JSON.stringify(body),
      });
      if (!result.ok || !result.data.id) {
        setError(accessError(result.status, apiErrorMessage(result.data, "Unable to save this plan.")));
        return;
      }
      const statusResult = await api(`/super-admin/plans/${result.data.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: Number(values.status) }),
      });
      if (!statusResult.ok) {
        setError(accessError(statusResult.status, apiErrorMessage(statusResult.data, "The plan was saved, but its status did not update.")));
        return;
      }
      router.push(`/plans?saved=${mode === "create" ? "created" : "updated"}`);
      router.refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Network error.";
      setError(`Network error contacting the plan API. (${message})`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="panel-card resource-form" onSubmit={onSubmit} noValidate>
      {error ? <div className="alert alert-danger">{error}</div> : null}
      <div className="resource-fields">
        <label className="form-field">
          Plan name
          <input value={values.name} maxLength={255} onChange={(event) => setField("name", event.target.value)} required />
          {fieldErrors.name ? <span className="field-error">{fieldErrors.name}</span> : null}
        </label>
        <label className="form-field">
          Description
          <textarea value={values.description} maxLength={255} rows={3} onChange={(event) => setField("description", event.target.value)} />
          {fieldErrors.description ? <span className="field-error">{fieldErrors.description}</span> : null}
        </label>
        <label className="form-field">
          Currency
          <input value={currency} readOnly />
          <span className="field-hint">Taken from platform settings. Plans do not store a separate currency.</span>
        </label>
        <label className="form-field">
          Monthly price
          <input inputMode="decimal" value={values.monthly_price} onChange={(event) => setField("monthly_price", event.target.value)} />
          {fieldErrors.monthly_price ? <span className="field-error">{fieldErrors.monthly_price}</span> : null}
        </label>
        <label className="form-field">
          Yearly price
          <input inputMode="decimal" value={values.yearly_price} onChange={(event) => setField("yearly_price", event.target.value)} />
          {fieldErrors.yearly_price ? <span className="field-error">{fieldErrors.yearly_price}</span> : null}
        </label>
        <label className="form-field">
          Billing duration
          <input value="Monthly and yearly" readOnly />
          <span className="field-hint">The duration is chosen when this plan is assigned to a school.</span>
        </label>
        <label className="form-field">
          Student limit
          <input inputMode="numeric" value={values.student_limit} placeholder="Unlimited" onChange={(event) => setField("student_limit", event.target.value)} />
          {fieldErrors.student_limit ? <span className="field-error">{fieldErrors.student_limit}</span> : null}
        </label>
        <label className="form-field">
          Staff / teacher limit
          <input inputMode="numeric" value={values.staff_limit} placeholder="Unlimited" onChange={(event) => setField("staff_limit", event.target.value)} />
          {fieldErrors.staff_limit ? <span className="field-error">{fieldErrors.staff_limit}</span> : null}
        </label>
        <label className="form-field">
          Plan status
          <select value={values.status} onChange={(event) => setField("status", event.target.value as "0" | "1")}>
            <option value="1">Active</option>
            <option value="0">Inactive</option>
          </select>
        </label>
      </div>
      <div className="page-actions">
        <button className="btn-pill btn-pill-green" type="submit" disabled={saving}>
          {saving ? "Saving…" : mode === "create" ? "Create plan" : "Save plan"}
        </button>
        <button className="btn-pill btn-pill-green-soft" type="button" onClick={() => router.push("/plans")}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function validate(values: Values): Errors {
  const errors: Errors = {};
  if (!values.name.trim()) errors.name = "Plan name is required.";
  else if (values.name.trim().length > 255) errors.name = "Plan name must be 255 characters or fewer.";
  if (values.description.trim().length > 255) errors.description = "Description must be 255 characters or fewer.";
  const monthly = numberError(values.monthly_price, "Monthly price");
  const yearly = numberError(values.yearly_price, "Yearly price");
  if (monthly) errors.monthly_price = monthly;
  if (yearly) errors.yearly_price = yearly;
  const students = limitError(values.student_limit, "Student limit");
  const staff = limitError(values.staff_limit, "Staff limit");
  if (students) errors.student_limit = students;
  if (staff) errors.staff_limit = staff;
  return errors;
}

function numberError(value: string, label: string): string | undefined {
  if (value.trim() === "") return `${label} is required.`;
  const amount = Number(value);
  if (!Number.isFinite(amount)) return `${label} must be a number.`;
  if (amount < 0) return `${label} cannot be negative.`;
  return undefined;
}

function limitError(value: string, label: string): string | undefined {
  if (value.trim() === "") return undefined;
  if (!/^\d+$/.test(value.trim())) return `${label} must be a whole number.`;
  return undefined;
}
