import type { Metadata } from "next";
import { LocalSiteFallback } from "@/components/domains/LocalSiteFallback";
import { SchoolLanding, SchoolNotFound, SiteBeingSetUp } from "@/components/domains/SchoolLanding";
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
  if (domainsMode() === "pending") return { title: "Website being set up", robots: { index: false, follow: false } };
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
    const loginUrl = `${app}/login?school=${encodeURIComponent(slug)}`;
    // The backend can't look schools up publicly yet: a neutral page, never sample data.
    if (domainsMode() === "pending" && !slugProblem(slug)) return <SiteBeingSetUp host={schoolHost(slug, rootDomain())} loginUrl={loginUrl} />;
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
