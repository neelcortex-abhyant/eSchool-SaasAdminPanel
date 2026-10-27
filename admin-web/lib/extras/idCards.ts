/**
 * ID card text, separate for students and staff. The server keeps one settings record per school
 * (/school-admin/id-card-settings: front_template, back_template, show_fields), so both layouts
 * are saved in `show_fields` as {"student": {...}, "staff": {...}}. front_template/back_template
 * keep the student text for anything else that reads them.
 */
import type { Raw } from "@/lib/extras/api";

export type CardKind = "student" | "staff";
export type CardSides = { front: string; back: string };
export type IdCardSettings = Record<CardKind, CardSides>;

function sides(value: unknown): CardSides | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  return { front: typeof row.front === "string" ? row.front : "", back: typeof row.back === "string" ? row.back : "" };
}

/** Reads the server's settings; older single-text settings apply to both kinds of card. */
export function parseIdCardSettings(raw: Raw | null | undefined): IdCardSettings {
  const shared: CardSides = { front: typeof raw?.front_template === "string" ? raw.front_template : "", back: typeof raw?.back_template === "string" ? raw.back_template : "" };
  let stored: Record<string, unknown> = {};
  try {
    const text = raw?.show_fields_json;
    const parsed = typeof text === "string" && text ? JSON.parse(text) : raw?.show_fields;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) stored = parsed as Record<string, unknown>;
  } catch {
    // Not our JSON; fall back to the shared text.
  }
  return { student: sides(stored.student) ?? shared, staff: sides(stored.staff) ?? shared };
}

/** The PUT body for both layouts. */
export function idCardBody(settings: IdCardSettings): Raw {
  const clean = (value: CardSides) => ({ front: value.front.trim(), back: value.back.trim() });
  return {
    front_template: clean(settings.student).front || null,
    back_template: clean(settings.student).back || null,
    show_fields: { student: clean(settings.student), staff: clean(settings.staff) },
  };
}

export const CARD_PLACEHOLDERS: Record<CardKind, string[]> = {
  student: ["{name}", "{class}", "{roll_number}", "{admission_no}", "{guardian}", "{session}"],
  staff: ["{name}", "{designation}", "{employee_id}", "{department}"],
};
