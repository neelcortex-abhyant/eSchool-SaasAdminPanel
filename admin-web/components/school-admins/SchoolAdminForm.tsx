"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiErrorMessage } from "@/lib/api";
import { loadSchools, type SchoolRecord } from "@/lib/school";
import {
  createSchoolAdminUser,
  loadSchoolAdminRoles,
  updateSchoolAdminUser,
} from "@/lib/schoolAdminUsers/api";
import type { SchoolAdminFormValues, SchoolAdminUser } from "@/lib/schoolAdminUsers/types";
import {
  applySchoolAdminApiFieldErrors,
  validateSchoolAdminForm,
  type SchoolAdminFieldErrors,
} from "@/lib/schoolAdminUsers/validation";

export function SchoolAdminForm({
  mode,
  initial,
  adminId,
  existingEmail,
}: {
  mode: "create" | "edit";
  initial: SchoolAdminFormValues;
  adminId?: string;
  existingEmail?: string;
}) {
  const router = useRouter();
  const [values, setValues] = useState(initial);
  const [fieldErrors, setFieldErrors] = useState<SchoolAdminFieldErrors>({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [schools, setSchools] = useState<SchoolRecord[]>([]);
  const [roles, setRoles] = useState<{ key: string; label: string }[]>([]);
  const [loadingMeta, setLoadingMeta] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function loadMeta() {
      setLoadingMeta(true);
      const [schoolsResult, rolesResult] = await Promise.all([
        loadSchools({ page: 1, pageSize: 100, sort: "name", order: "asc" }),
        loadSchoolAdminRoles(),
      ]);
      if (cancelled) return;
      if (schoolsResult.ok) setSchools(schoolsResult.data.items || []);
      if (rolesResult.ok) {
        setRoles((rolesResult.data.items || []).map((r) => ({ key: r.key, label: r.label })));
      }
      setLoadingMeta(false);
    }
    void loadMeta();
    return () => {
      cancelled = true;
    };
  }, []);

  function setField<K extends keyof SchoolAdminFormValues>(key: K, value: SchoolAdminFormValues[K]) {
    setValues((current) => ({ ...current, [key]: value }));
    setFieldErrors((current: SchoolAdminFieldErrors) => ({ ...current, [key]: undefined }));
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const errors = validateSchoolAdminForm(values, mode);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      setError("Fix the highlighted fields.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (mode === "create") {
        const result = await createSchoolAdminUser({
          first_name: values.first_name.trim(),
          last_name: values.last_name.trim(),
          email: values.email.trim(),
          mobile: values.mobile.trim() || null,
          school_id: Number(values.school_id),
          role_key: values.role_key,
          status: values.status === "1" ? 1 : 0,
          send_invitation: values.send_invitation,
        });
        if (!result.ok || !result.data.id) {
          setFieldErrors(applySchoolAdminApiFieldErrors(result.data));
          setError(apiErrorMessage(result.data, "Unable to create this school admin."));
          return;
        }
        router.push(`/school-admins/${result.data.id}?created=1`);
        router.refresh();
        return;
      }

      if (!adminId) return;
      const result = await updateSchoolAdminUser(adminId, {
        first_name: values.first_name.trim(),
        last_name: values.last_name.trim(),
        mobile: values.mobile.trim() || null,
        role_key: values.role_key,
        status: values.status === "1" ? 1 : 0,
        school_id: values.school_id ? Number(values.school_id) : undefined,
      });
      if (!result.ok) {
        setFieldErrors(applySchoolAdminApiFieldErrors(result.data));
        setError(apiErrorMessage(result.data, "Unable to save changes."));
        return;
      }
      router.push(`/school-admins/${adminId}?saved=1`);
      router.refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Network error.";
      setError(`Network error. (${message})`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="panel-card resource-form" onSubmit={onSubmit} noValidate>
      {error ? <div className="alert alert-danger">{error}</div> : null}
      {loadingMeta ? (
        <div className="skeleton" style={{ height: 120 }} />
      ) : (
        <div className="resource-fields">
          <Field
            label="First name"
            required
            value={values.first_name}
            error={fieldErrors.first_name}
            onChange={(v) => setField("first_name", v)}
          />
          <Field
            label="Last name"
            required
            value={values.last_name}
            error={fieldErrors.last_name}
            onChange={(v) => setField("last_name", v)}
          />
          {mode === "create" ? (
            <Field
              label="Email"
              required
              type="email"
              value={values.email}
              error={fieldErrors.email}
              onChange={(v) => setField("email", v)}
            />
          ) : (
            <div className="form-field">
              <label>Email</label>
              <input type="email" value={existingEmail || values.email} readOnly />
              <p className="field-hint">Email cannot be changed here.</p>
            </div>
          )}
          <Field
            label="Phone"
            value={values.mobile}
            error={fieldErrors.mobile}
            onChange={(v) => setField("mobile", v)}
          />
          <div className="form-field">
            <label htmlFor="sa-school">School *</label>
            <select
              id="sa-school"
              className={fieldErrors.school_id ? "invalid" : undefined}
              value={values.school_id}
              disabled={mode === "edit"}
              onChange={(e) => setField("school_id", e.target.value)}
            >
              <option value="">Select school</option>
              {schools.map((school) => (
                <option key={school.id} value={String(school.id)}>
                  {school.name || `School #${school.id}`}
                </option>
              ))}
            </select>
            {fieldErrors.school_id ? <p className="field-error">{fieldErrors.school_id}</p> : null}
            {mode === "edit" ? <p className="field-hint">School assignment is fixed after creation.</p> : null}
          </div>
          <div className="form-field">
            <label htmlFor="sa-role">Role *</label>
            <select
              id="sa-role"
              className={fieldErrors.role_key ? "invalid" : undefined}
              value={values.role_key}
              onChange={(e) => setField("role_key", e.target.value)}
            >
              {roles.map((role) => (
                <option key={role.key} value={role.key}>
                  {role.label}
                </option>
              ))}
            </select>
            {fieldErrors.role_key ? <p className="field-error">{fieldErrors.role_key}</p> : null}
          </div>
          <div className="form-field">
            <label htmlFor="sa-status">Account status *</label>
            <select
              id="sa-status"
              className={fieldErrors.status ? "invalid" : undefined}
              value={values.status}
              onChange={(e) => setField("status", e.target.value as "0" | "1")}
            >
              <option value="1">Active</option>
              <option value="0">Inactive</option>
            </select>
            {fieldErrors.status ? <p className="field-error">{fieldErrors.status}</p> : null}
          </div>
          {mode === "create" ? (
            <label className="profile-check field-span">
              <input
                type="checkbox"
                checked={values.send_invitation}
                onChange={(e) => setField("send_invitation", e.target.checked)}
              />
              Send secure invitation / password-setup email (no password shown in this form)
            </label>
          ) : null}
        </div>
      )}
      <p className="muted">
        {mode === "create"
          ? "Creates a school admin linked to the selected school. Access is enforced on the server — UI visibility is not sufficient on its own."
          : "Updates profile fields permitted by your super admin permissions."}
      </p>
      <div className="resource-actions">
        <button className="btn-pill btn-pill-green" type="submit" disabled={saving || loadingMeta}>
          {saving ? "Saving…" : mode === "create" ? "Create school admin" : "Save changes"}
        </button>
        <button
          className="btn-pill btn-pill-green-soft"
          type="button"
          onClick={() => router.push(adminId ? `/school-admins/${adminId}` : "/school-admins")}
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
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  type?: string;
  error?: string;
}) {
  const id = `sa-${label.toLowerCase().replace(/\s+/g, "-")}`;
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
        className={error ? "invalid" : undefined}
        aria-invalid={Boolean(error)}
        onChange={(e) => onChange(e.target.value)}
      />
      {error ? <p className="field-error">{error}</p> : null}
    </div>
  );
}

export function schoolAdminToFormValues(user: SchoolAdminUser): SchoolAdminFormValues {
  return {
    first_name: user.first_name,
    last_name: user.last_name,
    email: user.email,
    mobile: user.mobile || "",
    school_id: String(user.school_id),
    role_key: user.role_key,
    status: user.status === 1 ? "1" : "0",
    send_invitation: true,
  };
}
