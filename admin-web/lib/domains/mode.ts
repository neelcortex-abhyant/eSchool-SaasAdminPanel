/**
 * NEXT_PUBLIC_DOMAINS_API_MODE:
 *   unset (default)  Registration saves the subdomain/custom domain through the backend's live
 *                    domain fields; public school websites show "being set up" because the backend
 *                    has no public lookup route yet; admins can preview their site after signing in.
 *   "live"           Also uses the public lookup and domain routes in
 *                    backend/docs/SCHOOL_DOMAINS_API_CONTRACT.md.
 *   "mock"           Sample schools (lib/domains/mock-sites.json) and browser-only registrations.
 */
export type DomainsMode = "live" | "mock" | "pending";

export function domainsMode(): DomainsMode {
  const value = (process.env.NEXT_PUBLIC_DOMAINS_API_MODE || "").trim().toLowerCase();
  return value === "live" ? "live" : value === "mock" ? "mock" : "pending";
}

export function domainsLive(): boolean {
  return domainsMode() === "live";
}

export function domainsMock(): boolean {
  return domainsMode() === "mock";
}
