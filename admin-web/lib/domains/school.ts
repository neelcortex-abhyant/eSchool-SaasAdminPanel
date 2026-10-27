/**
 * The signed-in school's own record (GET /school-admin/school) as a website profile, for the
 * admin's preview and settings. Uses the backend's live domain fields: domain (full host),
 * domain_type ("default" | "custom") and domain_verified.
 */
import { api, apiErrorMessage } from "@/lib/api";
import { rootDomain } from "@/lib/domains/core";
import { cleanSite } from "@/lib/domains/sites";
import type { SchoolSite } from "@/lib/domains/types";

export type OwnSchool = {
  id: number;
  name: string;
  tagline?: string;
  logo?: string;
  address?: string;
  support_phone?: string;
  support_email?: string;
  status?: number;
  installed?: number;
  domain?: string | null;
  domain_type?: string | null;
  domain_verified?: number;
};

export async function ownSchool(): Promise<OwnSchool> {
  const result = await api<OwnSchool>("/school-admin/school");
  if (!result.ok) throw Object.assign(new Error(apiErrorMessage(result.data, "Unable to load your school.")), { status: result.status });
  return result.data;
}

/** The subdomain prefix of a default domain ("greenvalley.eschool.com" → "greenvalley"), else "". */
export function slugOf(school: Pick<OwnSchool, "domain" | "domain_type">): string {
  const host = (school.domain || "").toLowerCase();
  if (!host) return "";
  const root = rootDomain();
  if (school.domain_type === "default" || host.endsWith(`.${root}`)) return host.split(".")[0];
  return "";
}

export function siteFromSchool(school: OwnSchool): SchoolSite {
  const custom = school.domain_type === "custom" ? (school.domain || "").toLowerCase() : null;
  const site = cleanSite({
    school_id: school.id,
    name: school.name,
    slug: slugOf(school) || "your-school",
    tagline: school.tagline,
    logo: school.logo,
    // The backend keeps address, city, state and postal code in one line.
    address: school.address,
    city: null,
    phone: school.support_phone,
    email: school.support_email,
    admissions_open: true,
    status: school.status === 1 ? "active" : "pending_approval",
    setup_complete: school.status === 1 && school.installed === 1,
    custom_domain: custom,
    domain_status: custom ? (school.domain_verified ? "verified" : "pending") : "not_started",
  });
  return site as SchoolSite;
}
