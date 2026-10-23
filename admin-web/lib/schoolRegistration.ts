export type SchoolRegistrationValues = {
  name: string;
  support_email: string;
  support_phone: string;
  address: string;
  city: string;
  state: string;
  country: string;
  postal_code: string;
  domain: string;
  tagline: string;
  logo: string;
  admin_first_name: string;
  admin_last_name: string;
  admin_email: string;
  admin_mobile: string;
  admin_password: string;
  confirm_password: string;
  terms_accepted: boolean;
};

export const EMPTY_REGISTRATION: SchoolRegistrationValues = {
  name: "",
  support_email: "",
  support_phone: "",
  address: "",
  city: "",
  state: "",
  country: "",
  postal_code: "",
  domain: "",
  tagline: "",
  logo: "",
  admin_first_name: "",
  admin_last_name: "",
  admin_email: "",
  admin_mobile: "",
  admin_password: "",
  confirm_password: "",
  terms_accepted: false,
};

export type RegistrationErrors = Partial<Record<keyof SchoolRegistrationValues, string>>;

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function phoneError(value: string): string {
  const digits = value.replace(/\D/g, "");
  if (!/^[0-9]{6,15}$/.test(digits)) return "Enter a mobile number with 6 to 15 digits.";
  return "";
}

export function validateRegistration(values: SchoolRegistrationValues): RegistrationErrors {
  const errors: RegistrationErrors = {};
  if (!values.name.trim()) errors.name = "Enter the school name.";
  else if (values.name.trim().length > 255) errors.name = "School name must be 255 characters or fewer.";

  if (!EMAIL.test(values.support_email.trim())) errors.support_email = "Enter a valid school email address.";
  const schoolPhone = phoneError(values.support_phone);
  if (schoolPhone) errors.support_phone = schoolPhone;

  if (!values.address.trim()) errors.address = "Enter the school address.";
  if (!values.city.trim()) errors.city = "Enter the city.";
  if (!values.state.trim()) errors.state = "Enter the state.";
  if (!values.country.trim()) errors.country = "Enter the country.";
  if (values.postal_code.trim().length < 3) errors.postal_code = "Enter the postal code.";

  const composed = [values.address, values.city, values.state, values.postal_code, values.country]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(", ");
  if (composed.length > 255) {
    errors.address = "Address, city, state, country, and postal code together must be 255 characters or fewer.";
  }

  if (values.tagline.trim().length > 255) errors.tagline = "Tagline must be 255 characters or fewer.";
  const logo = values.logo.trim();
  if (logo.length > 255) errors.logo = "Logo must be 255 characters or fewer.";
  else if (logo && !logo.startsWith("http://") && !logo.startsWith("https://") && !logo.startsWith("/")) {
    errors.logo = "Logo must be an http(s) URL or a path starting with /.";
  }
  const domain = values.domain.trim();
  if (domain.length > 255) errors.domain = "Website must be 255 characters or fewer.";
  else if (domain && /\s/.test(domain)) errors.domain = "Website cannot contain spaces.";

  if (!values.admin_first_name.trim()) errors.admin_first_name = "Enter the administrator first name.";
  if (!values.admin_last_name.trim()) errors.admin_last_name = "Enter the administrator last name.";
  if (!EMAIL.test(values.admin_email.trim())) errors.admin_email = "Enter a valid administrator email.";
  const adminPhone = phoneError(values.admin_mobile);
  if (adminPhone) errors.admin_mobile = adminPhone;
  if (values.admin_password.length < 8) errors.admin_password = "Password must be at least 8 characters.";
  else if (values.admin_password.length > 128) errors.admin_password = "Password must be 128 characters or fewer.";
  if (values.admin_password !== values.confirm_password) errors.confirm_password = "Passwords do not match.";
  if (!values.terms_accepted) errors.terms_accepted = "Accept the terms and conditions to continue.";
  return errors;
}

export function registrationRequestBody(values: SchoolRegistrationValues) {
  return {
    name: values.name.trim(),
    support_email: values.support_email.trim(),
    support_phone: values.support_phone.trim(),
    address: values.address.trim(),
    city: values.city.trim(),
    state: values.state.trim(),
    country: values.country.trim(),
    postal_code: values.postal_code.trim(),
    tagline: values.tagline.trim(),
    logo: values.logo.trim(),
    domain: values.domain.trim() || null,
    admin_first_name: values.admin_first_name.trim(),
    admin_last_name: values.admin_last_name.trim(),
    admin_email: values.admin_email.trim(),
    admin_mobile: values.admin_mobile.trim(),
    admin_password: values.admin_password,
    terms_accepted: true,
  };
}
