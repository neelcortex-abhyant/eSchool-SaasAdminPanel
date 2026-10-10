export type SchoolFormValues = {
  name: string;
  code: string;
  address: string;
  support_email: string;
  support_phone: string;
  tagline: string;
  logo: string;
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
  logo: "",
  domain: "",
  status: "1",
  admin_first_name: "",
  admin_last_name: "",
  admin_password: "",
};

export type SchoolFieldErrors = Partial<Record<keyof SchoolFormValues, string>>;

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const CODE = /^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$/;

export function validateSchool(values: SchoolFormValues, mode: "create" | "edit"): SchoolFieldErrors {
  const errors: SchoolFieldErrors = {};
  const name = values.name.trim();
  if (!name) errors.name = "Enter the school name.";
  else if (name.length > 255) errors.name = "School name must be 255 characters or fewer.";

  const code = values.code.trim();
  if (!CODE.test(code)) {
    errors.code = "School code must be 2–64 letters, numbers, hyphens, or underscores.";
  }

  const address = values.address.trim();
  if (!address) errors.address = "Enter the school address.";
  else if (address.length > 255) errors.address = "Address must be 255 characters or fewer.";

  const email = values.support_email.trim();
  if (!EMAIL.test(email)) errors.support_email = "Enter a valid support email.";
  else if (email.length > 255) errors.support_email = "Email must be 255 characters or fewer.";

  const phoneDigits = values.support_phone.replace(/\D/g, "");
  if (!/^[0-9]{6,15}$/.test(phoneDigits)) errors.support_phone = "Phone must contain 6 to 15 digits.";

  if (values.tagline.trim().length > 255) errors.tagline = "Tagline must be 255 characters or fewer.";

  const domain = values.domain.trim();
  if (domain.length > 255) errors.domain = "Domain must be 255 characters or fewer.";
  else if (domain && /\s/.test(domain)) errors.domain = "Domain cannot contain spaces.";

  if (values.logo.trim().length > 255) errors.logo = "Logo must be 255 characters or fewer.";

  if (values.status !== "0" && values.status !== "1") errors.status = "Choose active or inactive.";

  if (mode === "create") {
    const first = values.admin_first_name.trim();
    const last = values.admin_last_name.trim();
    if (!first) errors.admin_first_name = "Enter the admin first name.";
    else if (first.length > 128) errors.admin_first_name = "First name must be 128 characters or fewer.";
    if (!last) errors.admin_last_name = "Enter the admin last name.";
    else if (last.length > 128) errors.admin_last_name = "Last name must be 128 characters or fewer.";
    if (values.admin_password.length < 8) errors.admin_password = "Admin password must be at least 8 characters.";
    else if (values.admin_password.length > 128) errors.admin_password = "Admin password must be 128 characters or fewer.";
  }

  return errors;
}

export function schoolRequestBody(values: SchoolFormValues) {
  return {
    name: values.name.trim(),
    code: values.code.trim(),
    address: values.address.trim(),
    support_email: values.support_email.trim(),
    support_phone: values.support_phone.trim(),
    tagline: values.tagline.trim(),
    logo: values.logo.trim(),
    domain: values.domain.trim(),
  };
}
