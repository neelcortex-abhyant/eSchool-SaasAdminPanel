import type { SchoolAdminFieldErrors, SchoolAdminFormValues } from "@/lib/schoolAdminUsers/types";

export type { SchoolAdminFieldErrors };

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateSchoolAdminForm(values: SchoolAdminFormValues, mode: "create" | "edit"): SchoolAdminFieldErrors {
  const errors: SchoolAdminFieldErrors = {};
  const first = values.first_name.trim();
  const last = values.last_name.trim();
  if (!first) errors.first_name = "Enter the admin first name.";
  else if (first.length > 128) errors.first_name = "First name must be 128 characters or fewer.";
  if (!last) errors.last_name = "Enter the admin last name.";
  else if (last.length > 128) errors.last_name = "Last name must be 128 characters or fewer.";

  const email = values.email.trim();
  if (mode === "create") {
    if (!EMAIL.test(email)) errors.email = "Enter a valid email address.";
    else if (email.length > 255) errors.email = "Email must be 255 characters or fewer.";
  }

  const mobile = values.mobile.trim();
  if (mobile && mobile.replace(/\D/g, "").length < 6) {
    errors.mobile = "Phone must contain at least 6 digits when provided.";
  } else if (mobile.length > 32) {
    errors.mobile = "Phone must be 32 characters or fewer.";
  }

  if (!values.school_id) errors.school_id = "Select a school.";
  if (!values.role_key) errors.role_key = "Select a role.";
  if (values.status !== "0" && values.status !== "1") errors.status = "Choose active or inactive.";

  return errors;
}

export function applySchoolAdminApiFieldErrors(data: unknown): SchoolAdminFieldErrors {
  if (!data || typeof data !== "object") return {};
  const record = data as Record<string, unknown>;
  const errors: SchoolAdminFieldErrors = {};
  if (typeof record.detail === "object" && record.detail !== null) {
    const detail = record.detail as Record<string, unknown>;
    for (const key of Object.keys(detail)) {
      const mapped = mapApiField(key);
      if (mapped && typeof detail[key] === "string") errors[mapped] = detail[key] as string;
    }
  }
  return errors;
}

function mapApiField(apiKey: string): keyof SchoolAdminFormValues | undefined {
  if (apiKey === "first_name" || apiKey === "last_name" || apiKey === "email" || apiKey === "mobile") return apiKey;
  if (apiKey === "school_id") return "school_id";
  if (apiKey === "role_key" || apiKey === "role") return "role_key";
  if (apiKey === "status") return "status";
  return undefined;
}
