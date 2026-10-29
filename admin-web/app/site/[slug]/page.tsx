import type { Metadata } from "next";
import { LocalSiteFallback } from "@/components/domains/LocalSiteFallback";
import { SchoolLanding, SchoolNotFound } from "@/components/domains/SchoolLanding";
import { rootDomain, schoolHost, slugProblem } from "@/lib/domains/core";
import { domainsMode } from "@/lib/domains/mode";
import { loginUrlFor, requestContext, schoolJsonLd, siteMetadata, siteUrlFor } from "@/lib/domains/page";
import { appOrigin } from "@/lib/domains/core";
import { siteBySlug } from "@/lib/domains/sites";

type Props = { params: Promise<{ slug: string }> };

async function load(slug: string) {
  if (slugProblem(slug)) return null;
  return siteBySlug(slug);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const { current } = await requestContext();
  const site = await load(slug).catch(() => null);
  return siteMetadata(site, site ? siteUrlFor(site, current) : "", schoolHost(slug));
}

/** A school's default site, served at {slug}.{root} (the middleware rewrites the host here). */
export default async function SchoolSitePage({ params }: Props) {
  const { slug } = await params;
  const { current } = await requestContext();
  let site;
  try {
    site = await load(slug);
  } catch {
    return (
      <div className="school-site ss-missing">
        <main className="ss-section">
          <h1>This school's website is temporarily unavailable</h1>
          <p>Please try again in a few minutes.</p>
        </main>
      </div>
    );
  }
  const app = appOrigin(current);
  if (!site) {
    // Sample data: a school registered in this browser is only stored in the browser.
    if (domainsMode() === "mock" && !slugProblem(slug)) return <LocalSiteFallback slug={slug} host={schoolHost(slug, rootDomain())} loginUrl={`${app}/login?school=${encodeURIComponent(slug)}`} appUrl={app} />;
    return <SchoolNotFound host={schoolHost(slug, rootDomain())} />;
  }
  const url = siteUrlFor(site, current);
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: schoolJsonLd(site, url) }} />
      <SchoolLanding site={site} loginUrl={loginUrlFor(site, current)} appUrl={app} />
    </>
  );
}
