"use client";

import Link from "next/link";
import { ChangeEvent, FormEvent, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import {
  EMPTY_REGISTRATION,
  registrationRequestBody,
  validateRegistration,
  type RegistrationErrors,
  type SchoolRegistrationValues,
} from "@/lib/schoolRegistration";

type RegistrationResult = {
  school_id?: number;
  status?: string;
  message?: string;
  detail?: unknown;
};

export default function RegisterSchoolForm() {
  const [values, setValues] = useState(EMPTY_REGISTRATION);
  const [errors, setErrors] = useState<RegistrationErrors>({});
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [done, setDone] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  function setField<K extends keyof SchoolRegistrationValues>(key: K, value: SchoolRegistrationValues[K]) {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  }

  async function onLogoFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploadingLogo(true);
    setFormError("");
    setErrors((current) => ({ ...current, logo: undefined }));
    try {
      const body = new FormData();
      body.set("file", file);
      const response = await fetch("/api/school-logos", { method: "POST", body });
      const data = (await response.json().catch(() => ({}))) as { logo?: string; detail?: string };
      if (!response.ok || typeof data.logo !== "string") {
        setErrors((current) => ({ ...current, logo: data.detail || "Unable to upload this logo." }));
        return;
      }
      setField("logo", data.logo);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Network error.";
      setErrors((current) => ({ ...current, logo: `Unable to upload this logo. (${message})` }));
    } finally {
      setUploadingLogo(false);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const nextErrors = validateRegistration(values);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      setFormError("Fix the highlighted fields.");
      return;
    }
    setSaving(true);
    setFormError("");
    let result;
    try {
      result = await api<RegistrationResult>("/schools/register", {
        method: "POST",
        body: JSON.stringify(registrationRequestBody(values)),
      });
    } catch {
      setFormError("Network error. Your entries are still here. Try again.");
      setSaving(false);
      return;
    }
    setSaving(false);
    if (!result.ok || result.data.status !== "pending_approval") {
      const fieldErrors = errorsFromApi(result.data);
      if (Object.keys(fieldErrors).length > 0) setErrors(fieldErrors);
      const message = apiErrorMessage(result.data, "Unable to submit this registration. Try again.");
      if (result.status === 409 && /school email/i.test(message)) {
        setErrors((current) => ({ ...current, support_email: message }));
      } else if (result.status === 409 && /already registered/i.test(message)) {
        setErrors((current) => ({ ...current, admin_email: message }));
      }
      setFormError(message);
      return;
    }
    setDone(true);
  }

  if (done) {
    return (
      <section className="panel-card register-result">
        <h2>Your school registration has been submitted successfully.</h2>
        <p>
          This school is pending approval. A platform administrator will review it. No subscription is
          started by this registration. After the school is activated, sign in with the administrator
          email and password.
        </p>
        <div className="page-actions">
          <Link className="btn-pill btn-pill-green" href="/login">
            Go to sign in
          </Link>
          <Link className="btn-pill btn-pill-green-soft" href="/">
            Back to home
          </Link>
        </div>
      </section>
    );
  }

  return (
    <form className="panel-card resource-form register-form" onSubmit={onSubmit} noValidate>
      {formError ? <div className="alert alert-danger">{formError}</div> : null}

      <fieldset className="register-section">
        <legend>School information</legend>
        <div className="resource-fields">
          <TextField label="School name" required value={values.name} error={errors.name} maxLength={255} onChange={(value) => setField("name", value)} />
          <TextField label="School email address" required type="email" value={values.support_email} error={errors.support_email} maxLength={255} onChange={(value) => setField("support_email", value)} />
          <TextField label="School mobile number" required value={values.support_phone} error={errors.support_phone} maxLength={32} onChange={(value) => setField("support_phone", value)} />
          <TextField label="School address" required value={values.address} error={errors.address} maxLength={255} onChange={(value) => setField("address", value)} />
          <TextField label="City" required value={values.city} error={errors.city} maxLength={80} onChange={(value) => setField("city", value)} />
          <TextField label="State" required value={values.state} error={errors.state} maxLength={80} onChange={(value) => setField("state", value)} />
          <TextField label="Country" required value={values.country} error={errors.country} maxLength={80} onChange={(value) => setField("country", value)} />
          <TextField label="Postal code" required value={values.postal_code} error={errors.postal_code} maxLength={16} onChange={(value) => setField("postal_code", value)} />
          <TextField label="School website" value={values.domain} error={errors.domain} maxLength={255} onChange={(value) => setField("domain", value)} />
          <TextField label="School tagline" value={values.tagline} error={errors.tagline} maxLength={255} onChange={(value) => setField("tagline", value)} />
          <div className="form-field field-span">
            <label htmlFor="reg-logo-file">School logo</label>
            <input
              id="reg-logo-file"
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              disabled={uploadingLogo || saving}
              onChange={(event) => void onLogoFile(event)}
            />
            <p className="field-hint">
              {uploadingLogo ? "Uploading logo…" : "Upload a PNG, JPEG, WEBP, or GIF up to 2 MB, or paste an image URL below."}
            </p>
            <label className="logo-url-label" htmlFor="reg-logo">
              Logo URL
            </label>
            <input id="reg-logo" value={values.logo} maxLength={255} placeholder="https://example.com/logo.png" aria-invalid={Boolean(errors.logo)} className={errors.logo ? "invalid" : undefined} onChange={(event) => setField("logo", event.target.value)} />
            {errors.logo ? <p className="field-error">{errors.logo}</p> : null}
            {values.logo.trim().startsWith("/") || /^https?:\/\//i.test(values.logo.trim()) ? (
              <img className="logo-preview" src={values.logo.trim()} alt="" />
            ) : null}
          </div>
        </div>
      </fieldset>

      <fieldset className="register-section">
        <legend>School administrator</legend>
        <div className="resource-fields">
          <TextField label="Administrator first name" required value={values.admin_first_name} error={errors.admin_first_name} maxLength={128} onChange={(value) => setField("admin_first_name", value)} />
          <TextField label="Administrator last name" required value={values.admin_last_name} error={errors.admin_last_name} maxLength={128} onChange={(value) => setField("admin_last_name", value)} />
          <TextField label="Administrator email" required type="email" value={values.admin_email} error={errors.admin_email} maxLength={255} onChange={(value) => setField("admin_email", value)} />
          <TextField label="Administrator mobile number" required value={values.admin_mobile} error={errors.admin_mobile} maxLength={32} onChange={(value) => setField("admin_mobile", value)} />
          <TextField label="Password" required type={showPassword ? "text" : "password"} value={values.admin_password} error={errors.admin_password} maxLength={128} autoComplete="new-password" onChange={(value) => setField("admin_password", value)} />
          <TextField label="Confirm password" required type={showPassword ? "text" : "password"} value={values.confirm_password} error={errors.confirm_password} maxLength={128} autoComplete="new-password" onChange={(value) => setField("confirm_password", value)} />
        </div>
        <button className="link-btn" type="button" onClick={() => setShowPassword((visible) => !visible)}>
          {showPassword ? "Hide passwords" : "Show passwords"}
        </button>
      </fieldset>

      <fieldset className="register-section">
        <legend>Terms</legend>
        <label className="register-terms">
          <input type="checkbox" checked={values.terms_accepted} onChange={(event) => setField("terms_accepted", event.target.checked)} />
          <span>
            I agree to the <Link href="/#contact">Terms and Conditions</Link> and <Link href="/#contact">Privacy Policy</Link>.
          </span>
        </label>
        {errors.terms_accepted ? <p className="field-error">{errors.terms_accepted}</p> : null}
        <p className="field-hint">Fields marked with * are required. Website, tagline, and logo are optional. Email verification and CAPTCHA are not part of this registration API.</p>
      </fieldset>

      <div className="resource-actions">
        <button className="btn-pill btn-register-school" type="submit" disabled={saving || uploadingLogo}>
          {saving ? "Submitting…" : uploadingLogo ? "Uploading logo…" : "Register your school"}
        </button>
        <Link className="btn-pill btn-pill-green-soft" href="/">
          Cancel
        </Link>
      </div>
    </form>
  );
}

function TextField({
  label,
  value,
  onChange,
  error,
  required,
  type = "text",
  maxLength,
  autoComplete,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  required?: boolean;
  type?: string;
  maxLength?: number;
  autoComplete?: string;
}) {
  const id = `reg-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
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
        aria-invalid={Boolean(error)}
        className={error ? "invalid" : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {error ? <p className="field-error">{error}</p> : null}
    </div>
  );
}

function errorsFromApi(data: unknown): RegistrationErrors {
  if (!data || typeof data !== "object") return {};
  const detail = (data as { detail?: unknown }).detail;
  if (!Array.isArray(detail)) return {};
  const errors: RegistrationErrors = {};
  for (const item of detail) {
    if (!item || typeof item !== "object") continue;
    const loc = (item as { loc?: unknown }).loc;
    const msg = (item as { msg?: unknown }).msg;
    if (!Array.isArray(loc) || typeof msg !== "string") continue;
    const field = String(loc[loc.length - 1] || "");
    if (field in EMPTY_REGISTRATION) {
      errors[field as keyof SchoolRegistrationValues] = msg.replace(/^Value error,\s*/i, "");
    }
  }
  return errors;
}
