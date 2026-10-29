/**
 * Picks live or sample data for grading and report cards, fees, and transport.
 *
 * NEXT_PUBLIC_OPS_API_MODE:
 *   "mock" (default)  every module uses sample data kept in this browser
 *   "live"            every module calls the school-admin routes on the server (grading
 *                     scales and report cards, fees, transport; added in backend 0039)
 *   per module        e.g. "fees:live,transport:mock"
 */
export type OpsModule = "grading" | "fees" | "transport";
export type ApiSource = "live" | "mock";

export const OPS_MODULES: OpsModule[] = ["grading", "fees", "transport"];

export function parseOpsMode(raw: string | undefined): Record<OpsModule, ApiSource> {
  const value = (raw || "").trim().toLowerCase();
  const all = (source: ApiSource) => Object.fromEntries(OPS_MODULES.map((m) => [m, source])) as Record<OpsModule, ApiSource>;
  if (value === "live") return all("live");
  const sources = all("mock");
  for (const part of value.split(",")) {
    const [module, source] = part.split(":").map((s) => s.trim());
    if ((OPS_MODULES as string[]).includes(module) && (source === "live" || source === "mock")) sources[module as OpsModule] = source;
  }
  return sources;
}

const SOURCES = parseOpsMode(process.env.NEXT_PUBLIC_OPS_API_MODE);

export function opsSource(module: OpsModule): ApiSource {
  return SOURCES[module];
}

export function isOpsLive(module: OpsModule): boolean {
  return SOURCES[module] === "live";
}
