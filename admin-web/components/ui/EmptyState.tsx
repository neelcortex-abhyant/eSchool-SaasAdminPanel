import type { ReactNode } from "react";

/** Centred message for a list or panel with nothing to show, with an optional action. */
export function EmptyState({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <p>{children}</p>
      {action}
    </div>
  );
}
