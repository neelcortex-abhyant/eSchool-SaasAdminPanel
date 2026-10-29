import type { Metadata } from "next";
import { SchoolLanding, SchoolNotFound } from "@/components/domains/SchoolLanding";
import { appOrigin, normalizeDomain } from "@/lib/domains/core";
import { loginUrlFor, requestContext, schoolJsonLd, siteMetadata, siteUrlFor } from "@/lib/domains/page";
import { siteByHost } from "@/lib/domains/sites";

type Props = { params: Promise<{ host: string }> };

async function load(raw: string) {
  const host = normalizeDomain(decodeURIComponent(raw));
  const site = await siteByHost(host).catch(() => null);
  // A custom domain shows the site only after its DNS ownership check has passed.
  return { host, site: site && site.custom_domain === host && site.domain_status === "verified" ? site : null };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { host } = await params;
  const { current } = await requestContext();
  const { site, host: clean } = await load(host);
  return siteMetadata(site, site ? siteUrlFor(site, current) : "", clean);
}

/** A school's site on its own verified domain (the middleware rewrites custom hosts here). */
export default async function CustomDomainSitePage({ params }: Props) {
  const { host } = await params;
  const { current } = await requestContext();
  const { site, host: clean } = await load(host);
  if (!site) return <SchoolNotFound host={clean} />;
  const url = siteUrlFor(site, current);
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: schoolJsonLd(site, url) }} />
      <SchoolLanding site={site} loginUrl={loginUrlFor(site, current)} appUrl={appOrigin(current)} />
    </>
  );
}
