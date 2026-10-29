"use client";

import { useEffect, useState } from "react";
import { api, getAccessToken, getMe } from "@/lib/api";

/**
 * "Finish setup" link, shown only to a signed-in admin of this school (checked against the
 * server); everyone else sees nothing. The site itself stays fully server-rendered.
 */
export function SetupIsland({ schoolId, appUrl, compact }: { schoolId: number; appUrl: string; compact?: boolean }) {
  const [isAdmin, setIsAdmin] = useState(false);
  useEffect(() => {
    if (!getAccessToken()) return;
    let cancelled = false;
    void (async () => {
      const me = await getMe<{ role?: string }>().catch(() => null);
      if (!me?.ok || me.data.role !== "school_admin") return;
      const school = await api<{ id?: number }>("/school-admin/school").catch(() => null);
      if (!cancelled && school?.ok && Number(school.data.id) === schoolId) setIsAdmin(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [schoolId]);
  if (!isAdmin) return null;
  return (
    <a className={`ss-admin-link${compact ? " is-compact" : ""}`} href={`${appUrl}/school/website`}>
      {compact ? "Manage website" : "Finish setup →"}
    </a>
  );
}
