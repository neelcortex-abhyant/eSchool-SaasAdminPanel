"use client";

import { useCallback } from "react";
import { useOptions } from "@/components/academics/hooks";
import { peopleService } from "@/lib/people";

export const TRANSPORT_TABS = [
  { href: "/school/transport/vehicles", label: "Vehicles" },
  { href: "/school/transport/routes", label: "Routes & stops" },
  { href: "/school/transport/assignments", label: "Student transport" },
];

/** Staff who can drive or help, with drivers and helpers (by designation) listed first. */
export function useTransportStaff(enabled = true) {
  const load = useCallback(async () => {
      const rows = [];
      for (let page = 1; page <= 10; page += 1) {
        const data = await peopleService("staff").listEmployees("staff", { page, pageSize: 50, status: "1" });
        rows.push(...data.items);
        if (rows.length >= data.total || data.items.length === 0) break;
      }
      const rank = (designation: string) => (/driver/i.test(designation) ? 0 : /helper|attendant|conductor/i.test(designation) ? 1 : 2);
      return rows.sort((a, b) => rank(a.designation) - rank(b.designation) || a.name.localeCompare(b.name));
  }, []);
  return useOptions(enabled ? load : null);
}
