"use client";

import { useCallback } from "react";
import { useOptions } from "@/components/academics/hooks";
import { peopleService } from "@/lib/people";
import { staffDirectory } from "@/lib/extras/api";
import { isOpsLive } from "@/lib/ops/mode";

export const TRANSPORT_TABS = [
  { href: "/school/transport/vehicles", label: "Vehicles" },
  { href: "/school/transport/routes", label: "Routes & stops" },
  { href: "/school/transport/assignments", label: "Student transport" },
];

/** Staff who can drive or help, with drivers and helpers (by designation) listed first. */
export function useTransportStaff(enabled = true) {
  const load = useCallback(async () => {
    // The server stores a vehicle's driver and helper as staff record ids, not user ids.
    if (isOpsLive("transport")) {
      const people = await staffDirectory();
      const rank = (designation: string) => (/driver/i.test(designation) ? 0 : /helper|attendant|conductor/i.test(designation) ? 1 : 2);
      return people.map((row) => ({ id: row.staff_id, name: row.name, designation: row.designation })).sort((a, b) => rank(a.designation) - rank(b.designation) || a.name.localeCompare(b.name));
    }
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
