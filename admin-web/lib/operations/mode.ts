/**
 * Live or sample data for the operations modules whose backend routes aren't deployed yet
 * (see backend/docs/OPERATIONS_MODULES_API_CONTRACT.md).
 *
 * NEXT_PUBLIC_OPERATIONS_API_MODE:
 *   unset (default)   every feature uses the server's routes (all deployed from backend 0043)
 *   "mock"            every feature below uses sample data kept in this browser
 *   "live"            same as unset
 *   per feature       e.g. "tracking:live,messaging:mock"
 *
 * Features that already have backend routes (staff attendance, leave, announcements,
 * notifications, certificates, ID cards, vehicles, routes) always use the server; only the
 * parts the server lacks are listed here.
 */
export type OperationsFeature = "tracking" | "payroll" | "messaging" | "notices";
export type ApiSource = "live" | "mock";

export const OPERATIONS_FEATURES: OperationsFeature[] = ["tracking", "payroll", "messaging", "notices"];

export function parseOperationsMode(raw: string | undefined): Record<OperationsFeature, ApiSource> {
  const value = (raw || "").trim().toLowerCase();
  const all = (source: ApiSource) => Object.fromEntries(OPERATIONS_FEATURES.map((f) => [f, source])) as Record<OperationsFeature, ApiSource>;
  if (value === "live") return all("live");
  if (value === "mock") return all("mock");
  // Every feature's routes are on the server (backend 0043); a per-feature list can still pick sample data.
  const sources: Record<OperationsFeature, ApiSource> = all("live");
  for (const part of value.split(",")) {
    const [feature, source] = part.split(":").map((s) => s.trim());
    if ((OPERATIONS_FEATURES as string[]).includes(feature) && (source === "live" || source === "mock")) sources[feature as OperationsFeature] = source;
  }
  return sources;
}

const SOURCES = parseOperationsMode(process.env.NEXT_PUBLIC_OPERATIONS_API_MODE);

/** Shown on the tracking pages when trips come from the server. */
export const TRACKING_LIVE_NOTE = "Bus positions come from the drivers' app. A bus with no fix in the last few minutes is shown as stale or offline.";

export function isOperationsLive(feature: OperationsFeature): boolean {
  return SOURCES[feature] === "live";
}

export const OPERATIONS_SAMPLE_NOTE: Record<OperationsFeature, string> = {
  tracking: "Live bus locations, trips and boarding records aren't on the school's server yet, so this page shows sample data built from your real vehicles and routes.",
  payroll: "Salary components, payroll processing and payslips aren't on the school's server yet, so this page uses sample data saved only in this browser.",
  messaging: "Teacher–parent messages aren't on the school's server yet, so this inbox shows sample conversations saved only in this browser.",
  notices: "Announcements and notifications are saved on the school's server. The server doesn't keep the audience, publish date, drafts or delivery status yet, so those are kept in this browser until it does.",
};
