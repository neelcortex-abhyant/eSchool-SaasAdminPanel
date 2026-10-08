"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { adminApi, adminErrorMessage } from "@/lib/adminApi";

export type SchoolFormValues = {
  name: string;
  code: string;
  address: string;
  support_email: string;
  support_phone: string;
  tagline: string;
  domain: string;
  status: string;
  admin_first_name: string;
  admin_last_name: string;
  admin_password: string;
};

export const EMPTY_SCHOOL_FORM: SchoolFormValues = {
  name: "",
  code: "",
  address: "",
  support_email: "",
  support_phone: "",
  tagline: "",
  domain: "",
  status: "1",
  admin_first_name: "",
  admin_last_name: "",
  admin_password: "",
};

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const CODE = /^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$/;
const PHONE = /^[0-9]{6,15}$/;

export function validateSchool(values: SchoolFormValues, mode: "create" | "edit"): string {
  if (!values.name.trim()) return "Enter the school name.";
  if (!CODE.test(values.code.trim())) {
    return "School code must be 2–64 letters, numbers, hyphens, or underscores.";
  }
  if (!values.address.trim()) return "Enter the school address.";
  if (!EMAIL.test(values.support_email.trim())) return "Enter a valid support email.";
  if (!PHONE.test(values.support_phone.trim())) return "Support phone must be 6 to 15 digits.";
  if (!values.tagline.trim()) return "Enter a tagline.";
  if (values.status !== "0" && values.status !== "1") return "Choose active or inactive.";
  if (mode === "create") {
    if (!values.admin_first_name.trim() || !values.admin_last_name.trim()) {
      return "Enter the school admin first and last name.";
    }
    if (values.admin_password.length < 8) return "School admin password must be at least 8 characters.";
  }
  return "";
}

export function SchoolForm({
  mode,
  initial,
  schoolId,
}: {
  mode: "create" | "edit";
  initial: SchoolFormValues;
  schoolId?: number;
}) {
  const router = useRouter();
  const [values, setValues] = useState(initial);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function setField(key: keyof SchoolFormValues, value: string) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const message = validateSchool(values, mode);
    if (message) {
      setError(message);
      return;
    }
    setSaving(true);
    setError("");
    const body: Record<string, unknown> = {
      name: values.name.trim(),
      code: values.code.trim(),
      address: values.address.trim(),
      support_email: values.support_email.trim(),
      support_phone: values.support_phone.trim(),
      tagline: values.tagline.trim(),
      domain: values.domain.trim() || null,
      status: Number(values.status),
    };
    if (mode === "create") {
      body.admin_first_name = values.admin_first_name.trim();
      body.admin_last_name = values.admin_last_name.trim();
      body.admin_password = values.admin_password;
    }
    const result = await adminApi<{ data?: { id?: number }; detail?: string; message?: string }>(
      mode === "create" ? "/schools" : `/schools/${schoolId}`,
      { method: mode === "create" ? "POST" : "PATCH", body: JSON.stringify(body) },
    );
    setSaving(false);
    if (!result.ok || !result.data.data?.id) {
      setError(adminErrorMessage(result.data, "Unable to save this school."));
      return;
    }
    router.push(`/schools/${result.data.data.id}`);
    router.refresh();
  }

  return (
    <form className="panel-card resource-form" onSubmit={onSubmit}>
      {error ? <div className="alert alert-danger">{error}</div> : null}
      <div className="resource-fields">
        <Field label="School name" required value={values.name} onChange={(value) => setField("name", value)} />
        <Field label="School code" required value={values.code} onChange={(value) => setField("code", value)} />
        <Field label="Address" required value={values.address} onChange={(value) => setField("address", value)} />
        <Field
          label="Support email"
          required
          type="email"
          value={values.support_email}
          onChange={(value) => setField("support_email", value)}
        />
        <Field
          label="Support phone"
          required
          value={values.support_phone}
          onChange={(value) => setField("support_phone", value)}
        />
        <Field label="Tagline" required value={values.tagline} onChange={(value) => setField("tagline", value)} />
        <Field label="Domain" value={values.domain} onChange={(value) => setField("domain", value)} />
        <div className="form-field">
          <label htmlFor="school-status">Status *</label>
          <select id="school-status" value={values.status} onChange={(event) => setField("status", event.target.value)}>
            <option value="1">Active</option>
            <option value="0">Inactive</option>
          </select>
        </div>
        {mode === "create" ? (
          <>
            <Field
              label="Admin first name"
              required
              value={values.admin_first_name}
              onChange={(value) => setField("admin_first_name", value)}
            />
            <Field
              label="Admin last name"
              required
              value={values.admin_last_name}
              onChange={(value) => setField("admin_last_name", value)}
            />
            <Field
              label="Admin password"
              required
              type="password"
              value={values.admin_password}
              onChange={(value) => setField("admin_password", value)}
            />
          </>
        ) : null}
      </div>
      <p className="muted">
        {mode === "create"
          ? "This creates the school and its admin account on the shared database. The new school appears in the school list."
          : "Saving updates this school. The support email and phone are also applied to the linked school admin."}
      </p>
      <div className="resource-actions">
        <button className="btn-pill btn-pill-green" type="submit" disabled={saving}>
          {saving ? "Saving…" : mode === "create" ? "Create school" : "Save changes"}
        </button>
        <button className="btn-pill btn-pill-green-soft" type="button" onClick={() => router.push(mode === "edit" && schoolId ? `/schools/${schoolId}` : "/schools")}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function Field({
  label,
  value,
  onChange,
  required,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  type?: string;
}) {
  const id = `school-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="form-field">
      <label htmlFor={id}>
        {label}
        {required ? " *" : ""}
      </label>
      <input id={id} type={type} value={value} onChange={(event) => onChange(event.target.value)} required={required} />
    </div>
  );
}
