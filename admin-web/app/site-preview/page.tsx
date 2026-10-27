"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { SchoolLanding } from "@/components/domains/SchoolLanding";
import { rootDomain, schoolHost } from "@/lib/domains/core";
import { ownSchool, siteFromSchool, slugOf } from "@/lib/domains/school";
import type { SchoolSite } from "@/lib/domains/types";

/**
 * The signed-in school admin's own website, built from their school's real record
 * (GET /school-admin/school). Visitors can't see this; it's a preview until the backend can serve
 * school websites publicly.
 */
export default function SitePreviewPage() {
  const [state, setState] = useState<{ site: SchoolSite; host: string } | { error: string; status?: number } | null>(null);

  useEffect(() => {
    document.title = "Website preview";
    ownSchool()
      .then((school) => {
        const slug = slugOf(school);
        setState({ site: siteFromSchool(school), host: school.domain_type === "custom" && school.domain ? school.domain : slug ? schoolHost(slug, rootDomain()) : "" });
      })
      .catch((error: Error & { status?: number }) => setState({ error: error.message, status: error.status }));
  }, []);

  if (!state) return <div className="school-site ss-loading" aria-busy="true" />;
  if ("error" in state) {
    return (
      <div className="school-site ss-missing">
        <main className="ss-section">
          <h1>Website preview</h1>
          <p>{state.status === 401 ? "Sign in as the school's admin to preview its website." : state.status === 403 ? "Only a school admin can preview the school's website." : state.error}</p>
          <p className="ss-hero-actions">
            <Link className="ss-btn ss-btn-primary" href={state.status === 401 ? "/login?next=/site-preview" : "/school"}>
              {state.status === 401 ? "Sign in" : "Back to the dashboard"}
            </Link>
          </p>
        </main>
      </div>
    );
  }
  return (
    <>
      <div className="ss-preview-bar" role="note">
        <span>
          <strong>Preview</strong> — only you can see this. {state.host ? <>Your website's address: {state.host}</> : "Your school has no website address yet."}
        </span>
        <Link href="/school/website">Back to Website & domain</Link>
      </div>
      <SchoolLanding site={state.site} loginUrl="/login" appUrl="" />
    </>
  );
}
