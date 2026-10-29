/** Browser-side checks for the people forms. The server runs the same rules and has the final say. */

export type Errors = Record<string, string>;

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function required(errors: Errors, field: string, value: string, message: string) {
  if (!value.trim()) errors[field] = message;
}

export function email(errors: Errors, field: string, value: string, isRequired: boolean) {
  const text = value.trim();
  if (!text) {
    if (isRequired) errors[field] = "Enter an email address.";
  } else if (!EMAIL.test(text)) errors[field] = "Enter a valid email address, like name@example.com.";
}

export function phone(errors: Errors, field: string, value: string, isRequired: boolean) {
  const text = value.trim();
  const digits = text.replace(/\D/g, "");
  if (!text) {
    if (isRequired) errors[field] = "Enter a phone number.";
  } else if (!/^\+?[0-9][0-9\s-]*$/.test(text) || digits.length < 7 || digits.length > 15) {
    errors[field] = "Enter a valid phone number (7 to 15 digits).";
  }
}

export function todayIso(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

/** Moves focus to the first field with an error, after React has rendered the messages. */
export function focusFirstError(form: HTMLElement | null) {
  window.setTimeout(() => {
    const field = form?.querySelector<HTMLElement>("[aria-invalid='true']");
    if (field) {
      field.scrollIntoView({ block: "center", behavior: "smooth" });
      field.focus({ preventScroll: true });
    } else {
      form?.querySelector<HTMLElement>(".alert-danger")?.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }, 0);
}
