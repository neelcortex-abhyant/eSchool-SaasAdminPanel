import type { ReactNode } from "react";

/** Page title row for Super Admin pages: icon, title and a one-line description. */
export function PageHeading({
  title,
  description,
  icon,
}: {
  title: string;
  description?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div className="page-heading-icon">{icon}</div>
      <div>
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
    </div>
  );
}
