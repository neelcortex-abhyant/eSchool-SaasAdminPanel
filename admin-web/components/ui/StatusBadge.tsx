export function StatusBadge({ active, activeLabel = "Active", inactiveLabel = "Inactive" }: { active: boolean; activeLabel?: string; inactiveLabel?: string }) {
  return <span className={`status-badge ${active ? "paid" : "refunded"}`}>{active ? activeLabel : inactiveLabel}</span>;
}
