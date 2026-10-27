"use client";

import { useEffect, useState } from "react";
import { SchoolLanding, SchoolNotFound } from "@/components/domains/SchoolLanding";
import { localSite } from "@/lib/domains/client";
import type { SchoolSite } from "@/lib/domains/types";

/**
 * Sample data only: a school registered in this browser has no server record, so its site is read
 * from this browser's storage. Live sites always come from the server.
 */
export function LocalSiteFallback({ slug, host, loginUrl, appUrl }: { slug: string; host: string; loginUrl: string; appUrl: string }) {
  const [site, setSite] = useState<SchoolSite | null | undefined>(undefined);
  useEffect(() => {
    const found = localSite(slug);
    setSite(found);
    // The server rendered "School not found" metadata because it can't see this browser's storage.
    if (found) document.title = found.name;
  }, [slug]);
  if (site === undefined) return <div className="school-site ss-loading" aria-busy="true" />;
  if (!site) return <SchoolNotFound host={host} />;
  return <SchoolLanding site={site} loginUrl={loginUrl} appUrl={appUrl} />;
}
