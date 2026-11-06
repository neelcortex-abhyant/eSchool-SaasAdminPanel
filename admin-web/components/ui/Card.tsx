import type { ReactNode } from "react";

/** White panel with the theme's border, radius and shadow; optional title row with actions. */
export function Card({ title, actions, children, className }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel-card${className ? ` ${className}` : ""}`}>
      {title || actions ? (
        <div className="panel-card-header">
          {title ? <h2>{title}</h2> : <span />}
          {actions}
        </div>
      ) : null}
      {children}
    </section>
  );
}
