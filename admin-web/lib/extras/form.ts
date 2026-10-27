/** Form values (strings) to and from the server's records, with the server's required-field checks. */
import type { FieldDef } from "@/lib/extras/types";
import type { Raw } from "@/lib/extras/api";

export type Values = Record<string, string>;

function fromServer(field: FieldDef, value: unknown): string {
  if (value === null || value === undefined) return field.initial ?? "";
  if (field.type === "checkbox") return value === true || value === 1 || value === "1" || value === "true" ? "1" : "0";
  const text = String(value);
  if (field.type === "date") return text.slice(0, 10);
  if (field.type === "time") return text.slice(0, 5);
  if (field.type === "datetime") return text.slice(0, 16);
  return text;
}

export function initialValues(fields: FieldDef[], row?: Raw | null): Values {
  return Object.fromEntries(fields.map((field) => [field.key, row ? fromServer(field, row[field.key]) : field.initial ?? (field.type === "checkbox" ? "0" : "")]));
}

export function problems(fields: FieldDef[], values: Values, editing: boolean): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const field of fields) {
    if (editing && field.createOnly) continue;
    const value = (values[field.key] ?? "").trim();
    if (field.required && !value && field.type !== "checkbox") {
      errors[field.key] = field.type === "ref" || field.type === "select" ? `Choose ${field.label.toLowerCase()}.` : `Enter ${field.label.toLowerCase()}.`;
      continue;
    }
    if (!value) continue;
    if (field.type === "number" && Number.isNaN(Number(value))) errors[field.key] = "Enter a number.";
    if (field.type === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) errors[field.key] = "Enter a valid email address.";
    if (field.type === "url" && !/^https?:\/\/\S+$/i.test(value)) errors[field.key] = "Enter a link starting with http:// or https://.";
  }
  return errors;
}

/** The request body: typed values, empty optional fields as null, create-only fields left out of edits. */
export function toBody(fields: FieldDef[], values: Values, editing: boolean): Raw {
  const body: Raw = {};
  for (const field of fields) {
    if (editing && field.createOnly) continue;
    const value = (values[field.key] ?? "").trim();
    if (field.type === "checkbox") body[field.key] = value === "1" ? 1 : 0;
    else if (!value) body[field.key] = null;
    else if (field.type === "number" || field.type === "ref") body[field.key] = Number(value);
    else if (field.type === "datetime") body[field.key] = value.length === 16 ? `${value}:00` : value;
    else body[field.key] = value;
  }
  return body;
}
