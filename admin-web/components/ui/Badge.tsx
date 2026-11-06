import type { ReactNode } from "react";

/** Status chip (green/amber/red/grey/blue) and the small count card used in summary rows. */
export type ChipTone = "green" | "amber" | "red" | "grey" | "blue";

const TONE_CLASS: Record<ChipTone, string> = { green: "paid", amber: "pending", red: "failed", grey: "refunded", blue: "info" };

export function Chip({ tone, children }: { tone: ChipTone; children: ReactNode }) {
  return <span className={`status-badge ${TONE_CLASS[tone]}`}>{children}</span>;
}

/** A count card for summary rows (attendance, homework). */
export function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: ChipTone }) {
  return (
    <div className={`teach-stat${tone ? ` is-${tone}` : ""}`}>
      <span className="teach-stat-value">{value}</span>
      <span className="teach-stat-label">{label}</span>
    </div>
  );
}

/**
 * A status chip from a table of known statuses. A value the table doesn't know (a new status
 * from the server) shows as a grey chip with its raw text instead of breaking the page.
 */
export function StatusChip<K extends string | number>({ map, value }: { map: Record<K, { label: string; tone: ChipTone }>; value: K | null | undefined }) {
  const known = value === null || value === undefined ? undefined : (map as Record<string | number, { label: string; tone: ChipTone } | undefined>)[value];
  return <Chip tone={known?.tone ?? "grey"}>{known?.label ?? (value === null || value === undefined || value === "" ? "—" : String(value))}</Chip>;
}
