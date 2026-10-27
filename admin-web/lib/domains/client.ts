/**
 * Browser-side domain calls.
 * Live (see backend/docs/SCHOOL_DOMAINS_API_CONTRACT.md):
 *   GET  /schools/subdomain-availability?slug=&name=&city=   (public, used during registration)
 *   GET  /school-admin/domain, PATCH /school-admin/domain {custom_domain}, POST /school-admin/domain/verify
 * Sample: availability against mock-sites.json and schools registered in this browser; settings kept
 * in this browser. Verification never succeeds on sample data (there's no DNS to check).
 */
import { api, apiErrorMessage } from "@/lib/api";
import { customDomainProblem, rootDomain, schoolHost, schoolSiteUrl, slugAlternatives, slugProblem } from "@/lib/domains/core";
import { domainsLive, domainsMode } from "@/lib/domains/mode";
import { ownSchool, siteFromSchool, slugOf } from "@/lib/domains/school";
import { SAMPLE_SITES, cleanSite } from "@/lib/domains/sites";
import type { Availability, DomainChoice, DomainSettings, SchoolSite } from "@/lib/domains/types";

const STORAGE_KEY = "school-sites-mock-v1";

type LocalSite = SchoolSite & { verification_token: string };

function localSites(): LocalSite[] {
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "[]") as LocalSite[];
  } catch {
    return [];
  }
}

function saveLocal(sites: LocalSite[]) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sites));
  } catch {
    // Storage unavailable: the sample site just won't persist.
  }
}

function takenLocally(slug: string): boolean {
  return SAMPLE_SITES.some((site) => site.slug === slug) || localSites().some((site) => site.slug === slug);
}

/** A school registered in this browser on sample data (the landing page reads it when the server has nothing). */
export function localSite(slug: string): SchoolSite | null {
  const site = localSites().find((item) => item.slug === slug);
  return site ? cleanSite(site as unknown as Record<string, unknown>) : null;
}

export async function checkAvailability(slug: string, context: { name?: string; city?: string } = {}): Promise<Availability> {
  const problem = slugProblem(slug);
  if (problem) return { slug, available: false, problem, suggestions: [] };
  // No availability route on the backend yet: registration's unique check decides on submit.
  if (domainsMode() === "pending") return { slug, available: true, problem: "", suggestions: [], unchecked: true };
  if (domainsMode() === "mock") {
    const available = !takenLocally(slug);
    return { slug, available, problem: available ? "" : `${schoolHost(slug)} is taken.`, suggestions: available ? [] : slugAlternatives(slug, context, takenLocally) };
  }
  const params = new URLSearchParams({ slug });
  if (context.name) params.set("name", context.name);
  if (context.city) params.set("city", context.city);
  const result = await api<Availability>(`/schools/subdomain-availability?${params}`);
  if (!result.ok) throw new Error(apiErrorMessage(result.data, "Unable to check the subdomain."));
  return { slug, available: Boolean(result.data.available), problem: result.data.problem || "", suggestions: Array.isArray(result.data.suggestions) ? result.data.suggestions : [] };
}

/**
 * The registration request's domain fields, as the backend takes them today: domain_type "default"
 * with the subdomain prefix in `domain` (the server adds its base domain), or "custom" with the
 * full hostname (unverified until the DNS check).
 */
export function domainRequestFields(choice: DomainChoice) {
  return choice.type === "default" ? { domain_type: "default", domain: choice.slug } : { domain_type: "custom", domain: choice.custom_domain };
}

function token(): string {
  const bytes = new Uint8Array(12);
  crypto.getRandomValues(bytes);
  return `eschool-verify-${Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")}`;
}

/** Sample data: keeps the registered school's public profile in this browser so its site opens right away. */
export function saveSampleSite(input: { name: string; slug: string; tagline: string; logo: string; address: string; city: string; phone: string; email: string; custom_domain: string | null }): SchoolSite {
  const sites = localSites().filter((site) => site.slug !== input.slug);
  const site: LocalSite = {
    school_id: Date.now(),
    name: input.name.trim(),
    slug: input.slug,
    tagline: input.tagline.trim() || null,
    logo: input.logo.trim() || null,
    address: input.address.trim() || null,
    city: input.city.trim() || null,
    phone: input.phone.trim() || null,
    email: input.email.trim() || null,
    theme_primary: null,
    theme_secondary: null,
    about: null,
    admissions_open: true,
    status: "pending_approval",
    setup_complete: false,
    custom_domain: input.custom_domain,
    domain_status: input.custom_domain ? "pending" : "not_started",
    verification_token: token(),
  };
  sites.push(site);
  saveLocal(sites);
  return cleanSite(site as unknown as Record<string, unknown>) as SchoolSite;
}

function settingsFor(site: { slug: string; custom_domain: string | null; domain_status: SchoolSite["domain_status"] }, verificationToken: string, lastError: string | null = null): DomainSettings {
  const root = rootDomain();
  return {
    slug: site.slug,
    default_url: schoolSiteUrl(site.slug, root, typeof window === "undefined" ? undefined : { protocol: window.location.protocol, port: window.location.port }),
    domain_type: site.custom_domain ? "custom" : "default",
    custom_domain: site.custom_domain,
    domain_status: site.domain_status,
    verification: site.custom_domain
      ? { txt_name: `_eschool-verify.${site.custom_domain}`, txt_value: verificationToken, cname_name: site.custom_domain, cname_target: schoolHost(site.slug, root) }
      : null,
    last_checked_at: null,
    last_error: lastError,
  };
}

const MOCK_SETTINGS_KEY = "school-domain-settings-mock-v1";

function mockSettings(): DomainSettings {
  try {
    const saved = window.localStorage.getItem(MOCK_SETTINGS_KEY);
    if (saved) return JSON.parse(saved) as DomainSettings;
  } catch {
    // fall through to the sample school
  }
  return settingsFor(SAMPLE_SITES[0], "eschool-verify-0a1b2c3d4e5f60718293a4b5");
}

function saveMockSettings(settings: DomainSettings) {
  try {
    window.localStorage.setItem(MOCK_SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // ignore
  }
}

/** Settings from the school's own record (domain, domain_type, domain_verified) until the domain routes exist. */
async function settingsFromSchool(): Promise<DomainSettings> {
  const school = await ownSchool();
  const site = siteFromSchool(school);
  const slug = slugOf(school);
  const here = typeof window === "undefined" ? undefined : { protocol: window.location.protocol, port: window.location.port };
  return {
    slug,
    default_url: slug ? schoolSiteUrl(slug, rootDomain(), here) : "",
    domain_type: school.domain_type === "custom" ? "custom" : "default",
    custom_domain: site.custom_domain,
    domain_status: site.domain_status,
    verification: null,
    last_checked_at: null,
    last_error: null,
  };
}

const NOT_YET = "Connecting or checking a custom domain isn't available on the school's server yet. Ask the platform team to set it up.";

export async function domainSettings(): Promise<DomainSettings> {
  if (domainsMode() === "pending") return settingsFromSchool();
  if (domainsMode() === "mock") return mockSettings();
  const result = await api<DomainSettings>("/school-admin/domain");
  if (!result.ok) throw Object.assign(new Error(apiErrorMessage(result.data, "Unable to load the school's domain.")), { status: result.status });
  return result.data;
}

export async function setCustomDomain(domain: string | null): Promise<DomainSettings> {
  if (domain !== null) {
    const problem = customDomainProblem(domain);
    if (problem) throw Object.assign(new Error(problem), { field: "custom_domain" });
  }
  if (domainsMode() === "pending") throw new Error(NOT_YET);
  if (domainsMode() === "mock") {
    const current = mockSettings();
    const next = settingsFor({ slug: current.slug, custom_domain: domain ? domain.trim().toLowerCase() : null, domain_status: domain ? "pending" : "not_started" }, current.verification?.txt_value ?? token());
    saveMockSettings(next);
    return next;
  }
  const result = await api<DomainSettings>("/school-admin/domain", { method: "PATCH", body: JSON.stringify({ custom_domain: domain }) });
  if (!result.ok) throw Object.assign(new Error(apiErrorMessage(result.data, "Unable to save the domain.")), { status: result.status });
  return result.data;
}

export async function verifyDomain(): Promise<DomainSettings> {
  if (domainsMode() === "pending") throw new Error(NOT_YET);
  if (domainsMode() === "mock") {
    const current = mockSettings();
    const next: DomainSettings = {
      ...current,
      domain_status: current.custom_domain ? "pending" : current.domain_status,
      last_checked_at: new Date().toISOString(),
      last_error: current.custom_domain ? "The TXT record wasn't found yet. DNS changes can take up to 48 hours to appear. (Sample data: verification never completes here.)" : null,
    };
    saveMockSettings(next);
    return next;
  }
  const result = await api<DomainSettings>("/school-admin/domain/verify", { method: "POST" });
  if (!result.ok) throw Object.assign(new Error(apiErrorMessage(result.data, "Unable to check the domain.")), { status: result.status });
  return result.data;
}

/** The signed-in school's public site profile (for the setup checklist). */
export async function mySite(slug: string): Promise<SchoolSite | null> {
  if (domainsMode() === "pending") return siteFromSchool(await ownSchool());
  if (domainsMode() === "mock") {
    const sample = SAMPLE_SITES.find((site) => site.slug === slug);
    return sample ? cleanSite(sample as unknown as Record<string, unknown>) : localSite(slug);
  }
  const result = await api<Record<string, unknown>>(`/public/schools/by-host?host=${encodeURIComponent(schoolHost(slug))}`);
  if (result.status === 404) return null;
  if (!result.ok) throw new Error(apiErrorMessage(result.data, "Unable to load the school website."));
  return cleanSite(result.data);
}
