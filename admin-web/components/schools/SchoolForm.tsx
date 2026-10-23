"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, apiErrorMessage, getAccessToken } from "@/lib/api";
import {
  applyApiFieldErrors,
  schoolRequestBody,
  validateSchool,
  type SchoolFieldErrors,
  type SchoolFormValues,
} from "@/lib/schoolForm";
import type { SchoolRecord } from "@/lib/school";

export type { SchoolFormValues } from "@/lib/schoolForm";
export { EMPTY_SCHOOL_FORM } from "@/lib/schoolForm";

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
  const [fieldErrors, setFieldErrors] = useState<SchoolFieldErrors>({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);

  function setField(key: keyof SchoolFormValues, value: string) {
    setValues((current) => ({ ...current, [key]: value }));
    setFieldErrors((current) => ({ ...current, [key]: undefined }));
  }

  async function onLogoFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploadingLogo(true);
    setError("");
    setFieldErrors((current) => ({ ...current, logo: undefined }));
    try {
      const body = new FormData();
      body.set("file", file);
      const token = getAccessToken();
      const response = await fetch("/api/school-logos", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body,
      });
      const data = (await response.json().catch(() => ({}))) as { logo?: string; detail?: string };
      if (!response.ok || typeof data.logo !== "string") {
        setFieldErrors((current) => ({ ...current, logo: data.detail || "Unable to upload this logo." }));
        return;
      }
      setField("logo", data.logo);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Network error.";
      setFieldErrors((current) => ({ ...current, logo: `Unable to upload this logo. (${message})` }));
    } finally {
      setUploadingLogo(false);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const errors = validateSchool(values, mode);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      setError("Fix the highlighted fields.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const result = await api<SchoolRecord>(mode === "create" ? "/super-admin/schools" : `/super-admin/schools/${schoolId}`, {
        method: mode === "create" ? "POST" : "PATCH",
        body: JSON.stringify(schoolRequestBody(values)),
      });
      if (!result.ok || !result.data.id) {
        setFieldErrors(applyApiFieldErrors(result.data));
        setError(apiErrorMessage(result.data, "Unable to save this school."));
        return;
      }
      const savedId = result.data.id;
      const warnings: string[] = [];

      if ((mode === "create" && values.status === "0") || (mode === "edit" && schoolId && values.status !== initial.status)) {
        const action = values.status === "1" ? "activate" : "suspend";
        const statusResult = await api<SchoolRecord>(`/super-admin/schools/${savedId}/${action}`, { method: "POST" });
        if (!statusResult.ok) warnings.push("status");
      }

      if (mode === "create") {
        const adminResult = await api(`/super-admin/schools/${savedId}/admins`, {
          method: "POST",
          body: JSON.stringify({
            email: values.support_email.trim(),
            password: values.admin_password,
            first_name: values.admin_first_name.trim(),
            last_name: values.admin_last_name.trim(),
            mobile: values.support_phone.trim().slice(0, 32),
          }),
        });
        if (!adminResult.ok) warnings.push("admin");
      }

      const query = new URLSearchParams({ saved: mode === "create" ? "created" : "updated" });
      if (warnings.length) query.set("warning", warnings.join(","));
      router.push(`/schools/${savedId}?${query.toString()}`);
      router.refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Network error. Try again.";
      setError(`Network error contacting the school API. (${message})`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="panel-card resource-form" onSubmit={onSubmit} noValidate>
      {error ? <div className="alert alert-danger">{error}</div> : null}
      <div className="resource-fields">
        <Field label="School name" required value={values.name} error={fieldErrors.name} maxLength={255} onChange={(value) => setField("name", value)} />
        <Field label="School code" required value={values.code} error={fieldErrors.code} maxLength={64} onChange={(value) => setField("code", value)} />
        <Field label="Address" required value={values.address} error={fieldErrors.address} maxLength={255} onChange={(value) => setField("address", value)} />
        <Field
          label="Support email"
          required
          type="email"
          value={values.support_email}
          error={fieldErrors.support_email}
          maxLength={255}
          onChange={(value) => setField("support_email", value)}
        />
        <Field
          label="Support phone"
          required
          value={values.support_phone}
          error={fieldErrors.support_phone}
          maxLength={255}
          onChange={(value) => setField("support_phone", value)}
        />
        <Field label="Tagline" value={values.tagline} error={fieldErrors.tagline} maxLength={255} onChange={(value) => setField("tagline", value)} />
        <Field label="Domain" value={values.domain} error={fieldErrors.domain} maxLength={255} onChange={(value) => setField("domain", value)} />
        <div className="form-field">
          <label htmlFor="school-status">Status *</label>
          <select
            id="school-status"
            className={fieldErrors.status ? "invalid" : undefined}
            aria-invalid={Boolean(fieldErrors.status)}
            value={values.status}
            onChange={(event) => setField("status", event.target.value)}
          >
            <option value="1">Active</option>
            <option value="0">Inactive</option>
          </select>
          {fieldErrors.status ? <p className="field-error">{fieldErrors.status}</p> : null}
        </div>
        <div className="form-field field-span">
          <label htmlFor="school-logo-file">Logo image</label>
          <input
            id="school-logo-file"
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            disabled={uploadingLogo || saving}
            onChange={(event) => void onLogoFile(event)}
          />
          <p className="field-hint">
            {uploadingLogo ? "Uploading logo…" : "Upload a PNG, JPEG, WEBP, or GIF up to 2 MB, or paste an image URL below."}
          </p>
          <label className="logo-url-label" htmlFor="school-logo">
            Logo URL
          </label>
          <input
            id="school-logo"
            type="text"
            value={values.logo}
            maxLength={255}
            className={fieldErrors.logo ? "invalid" : undefined}
            aria-invalid={Boolean(fieldErrors.logo)}
            placeholder="https://example.com/logo.png"
            onChange={(event) => setField("logo", event.target.value)}
          />
          {fieldErrors.logo ? <p className="field-error">{fieldErrors.logo}</p> : null}
          <LogoPreview value={values.logo} />
        </div>
        {mode === "create" ? (
          <>
            <Field
              label="Admin first name"
              required
              value={values.admin_first_name}
              error={fieldErrors.admin_first_name}
              maxLength={128}
              onChange={(value) => setField("admin_first_name", value)}
            />
            <Field
              label="Admin last name"
              required
              value={values.admin_last_name}
              error={fieldErrors.admin_last_name}
              maxLength={128}
              onChange={(value) => setField("admin_last_name", value)}
            />
            <Field
              label="Admin password"
              required
              type="password"
              value={values.admin_password}
              error={fieldErrors.admin_password}
              maxLength={128}
              autoComplete="new-password"
              onChange={(value) => setField("admin_password", value)}
            />
          </>
        ) : null}
      </div>
      <p className="muted">
        {mode === "create"
          ? "This creates the school and a school admin who can sign in to their own panel."
          : "Saving updates the school record. A status change is sent as activate or suspend."}
      </p>
      <div className="resource-actions">
        <button className="btn-pill btn-pill-green" type="submit" disabled={saving || uploadingLogo}>
          {saving ? "Saving…" : uploadingLogo ? "Uploading logo…" : mode === "create" ? "Create school" : "Save changes"}
        </button>
        <button
          className="btn-pill btn-pill-green-soft"
          type="button"
          onClick={() => router.push(mode === "edit" && schoolId ? `/schools/${schoolId}` : "/schools")}
        >
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
  error,
  maxLength,
  autoComplete,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  type?: string;
  error?: string;
  maxLength?: number;
  autoComplete?: string;
}) {
  const id = `school-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="form-field">
      <label htmlFor={id}>
        {label}
        {required ? " *" : ""}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        maxLength={maxLength}
        autoComplete={autoComplete}
        className={error ? "invalid" : undefined}
        aria-invalid={Boolean(error)}
        onChange={(event) => onChange(event.target.value)}
      />
      {error ? <p className="field-error">{error}</p> : null}
    </div>
  );
}

function LogoPreview({ value }: { value: string }) {
  const logo = value.trim();
  const show = Boolean(logo) && (/^https?:\/\//i.test(logo) || logo.startsWith("/"));
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [logo]);

  if (!show || failed) return null;
  return <img className="logo-preview" src={logo} alt="" onError={() => setFailed(true)} />;
}
