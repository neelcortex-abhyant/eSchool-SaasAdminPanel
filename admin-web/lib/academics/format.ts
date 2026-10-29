const DATE_FORMAT = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

/** "2026-04-01" → "1 Apr 2026". Dates are calendar dates, so they are read as UTC to avoid shifting a day. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(`${value.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : DATE_FORMAT.format(date);
}

export function toId(value: string): number | "" {
  return value === "" ? "" : Number(value);
}
