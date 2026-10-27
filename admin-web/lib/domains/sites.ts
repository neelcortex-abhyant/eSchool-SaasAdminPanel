/**
 * Finding a school's public site. Runs on the server (landing pages) and in the browser.
 * Live: GET /api/v1/public/schools/by-host?host= — public, safe profile fields only.
 * Sample (mode "mock" only): lib/domains/mock-sites.json; schools registered in this browser are read by the page itself.
 * Pending (default): the backend has no public lookup yet, so nothing is returned.
 */
import seed from "@/lib/domains/mock-sites.json";
import { normalizeDomain, rootDomain, schoolHost } from "@/lib/domains/core";
import { domainsMode } from "@/lib/domains/mode";
import type { DomainStatus, SchoolSite } from "@/lib/domains/types";

export const SAMPLE_SITES = seed.sites as SchoolSite[];

function backendBase(): string {
  return (process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "https://eschool-backend-8322.onrender.com").replace(/\/$/, "");
}

const COLOR = /^#[0-9a-f]{6}$/i;

/** Keeps only what the page may render: text trimmed, colours valid, links http(s) or site-relative. */
export function cleanSite(raw: Record<string, unknown>): SchoolSite | null {
  const text = (value: unknown, max = 500) => (typeof value === "string" && value.trim() ? value.trim().slice(0, max) : null);
  const name = text(raw.name, 120);
  const slug = text(raw.slug, 63);
  if (!name || !slug) return null;
  const logo = text(raw.logo, 500);
  const status = raw.status === "active" || raw.status === "inactive" ? raw.status : "pending_approval";
  const domainStatus = ["pending", "verified", "failed"].includes(String(raw.domain_status)) ? (raw.domain_status as DomainStatus) : "not_started";
  return {
    school_id: Number(raw.school_id) || 0,
    name,
    slug,
    tagline: text(raw.tagline, 160),
    logo: logo && (/^https:\/\//i.test(logo) || logo.startsWith("/")) ? logo : null,
    address: text(raw.address, 255),
    city: text(raw.city, 80),
    phone: text(raw.phone, 32),
    email: text(raw.email, 255) && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(raw.email).trim()) ? String(raw.email).trim() : null,
    theme_primary: COLOR.test(String(raw.theme_primary ?? "")) ? String(raw.theme_primary) : null,
    theme_secondary: COLOR.test(String(raw.theme_secondary ?? "")) ? String(raw.theme_secondary) : null,
    about: text(raw.about, 2000),
    admissions_open: raw.admissions_open !== false,
    status,
    setup_complete: raw.setup_complete === true,
    custom_domain: text(raw.custom_domain, 253),
    domain_status: domainStatus,
  };
}

/** The site for a host, or null when no school uses it (or its custom domain isn't verified yet). */
export async function siteByHost(host: string): Promise<SchoolSite | null> {
  const wanted = normalizeDomain(host);
  const mode = domainsMode();
  // No public lookup route on the backend yet: nothing to show (the page says it's being set up).
  if (mode === "pending") return null;
  if (mode === "mock") {
    const root = rootDomain();
    const site = SAMPLE_SITES.find((item) => schoolHost(item.slug, root) === wanted || (item.custom_domain === wanted && item.domain_status === "verified"));
    return site ? cleanSite(site as unknown as Record<string, unknown>) : null;
  }
  try {
    const response = await fetch(`${backendBase()}/api/v1/public/schools/by-host?host=${encodeURIComponent(wanted)}`, { next: { revalidate: 60 } });
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`by-host ${response.status}`);
    return cleanSite((await response.json()) as Record<string, unknown>);
  } catch (error) {
    // Let the page show "temporarily unavailable" rather than "not found" when the server is down.
    throw error instanceof Error ? error : new Error("Unable to load the school site.");
  }
}

export function siteBySlug(slug: string): Promise<SchoolSite | null> {
  return siteByHost(schoolHost(slug));
}
