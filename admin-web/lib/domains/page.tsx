/** Shared by the /site routes: request origin, metadata and structured data for a school site. */
import type { Metadata } from "next";
import { headers } from "next/headers";
import { appOrigin, rootDomain, schoolHost, schoolSiteUrl } from "@/lib/domains/core";
import type { SchoolSite } from "@/lib/domains/types";

export async function requestContext() {
  const list = await headers();
  const host = (list.get("x-forwarded-host") ?? list.get("host") ?? "").toLowerCase();
  const proto = list.get("x-forwarded-proto") ?? (host.startsWith("localhost") || host.includes(".localhost") ? "http" : "https");
  const port = host.includes(":") ? host.split(":").pop() ?? "" : "";
  return { host, current: { protocol: `${proto}:`, port } };
}

export function siteUrlFor(site: SchoolSite, current: { protocol: string; port: string }): string {
  if (site.custom_domain && site.domain_status === "verified") return `https://${site.custom_domain}`;
  return schoolSiteUrl(site.slug, rootDomain(), current);
}

export function loginUrlFor(site: SchoolSite, current: { protocol: string; port: string }): string {
  return `${appOrigin(current)}/login?school=${encodeURIComponent(site.slug)}`;
}

export function siteMetadata(site: SchoolSite | null, url: string, fallbackHost: string): Metadata {
  if (!site) return { title: "School not found", robots: { index: false, follow: false } };
  const location = [site.address, site.city].filter(Boolean).join(", ");
  const description = (site.tagline || site.about || `${site.name}${location ? `, ${location}` : ""} — admissions, contact details and portal login.`).slice(0, 160);
  return {
    title: { absolute: site.name },
    description,
    alternates: { canonical: url },
    openGraph: { type: "website", url, title: `Welcome to ${site.name}`, description, siteName: site.name, images: site.logo ? [{ url: site.logo, alt: `${site.name} logo` }] : undefined },
    twitter: { card: "summary", title: site.name, description },
    // An inactive school's site stays reachable but out of search results.
    robots: site.status === "inactive" ? { index: false, follow: false } : { index: true, follow: true },
    other: { "x-school-host": fallbackHost || schoolHost(site.slug) },
  };
}

/** schema.org School, so search engines show the name, address and contact. */
export function schoolJsonLd(site: SchoolSite, url: string): string {
  const data: Record<string, unknown> = { "@context": "https://schema.org", "@type": "School", name: site.name, url };
  if (site.logo) data.logo = site.logo;
  if (site.tagline || site.about) data.description = site.tagline || site.about;
  if (site.phone) data.telephone = site.phone;
  if (site.email) data.email = site.email;
  if (site.address || site.city) data.address = { "@type": "PostalAddress", streetAddress: site.address ?? undefined, addressLocality: site.city ?? undefined };
  // Escape "<" so the script can't be closed by profile text.
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
