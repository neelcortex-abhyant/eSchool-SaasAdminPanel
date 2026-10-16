import type { ReactNode } from "react";
import {
  IconBuilding,
  IconCheck,
  IconFees,
  IconPackage,
  IconTrend,
  IconUsers,
} from "@/lib/icons";
import type { StatCardData } from "@/lib/dashboardData";

const ICONS = {
  schools: IconBuilding,
  students: IconUsers,
  teachers: IconUsers,
  revenue: IconTrend,
  plans: IconPackage,
  payments: IconFees,
} as const;

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

export function StatCard({ data }: { data: StatCardData }) {
  const Icon = ICONS[data.icon];
  return (
    <article className="stat-card">
      <div className="stat-card-top">
        <div>
          <p className="stat-title">{data.title}</p>
          <p className="stat-value">{data.value}</p>
        </div>
        <div className={`stat-icon ${data.tone}`}>
          <Icon width={20} height={20} />
        </div>
      </div>
      <div className={`stat-meta ${data.meta.startsWith("↑") || data.meta.startsWith("+") ? "" : "is-muted"}`}>
        {(data.meta.startsWith("↑") || data.meta.startsWith("+")) && <IconCheck width={12} height={12} />}
        {data.meta}
      </div>
    </article>
  );
}

export function StatCardSkeleton() {
  return (
    <div className="stat-card">
      <div className="skeleton" style={{ height: 14, width: "40%", marginBottom: 12 }} />
      <div className="skeleton" style={{ height: 32, width: "55%", marginBottom: 12 }} />
      <div className="skeleton" style={{ height: 12, width: "70%" }} />
    </div>
  );
}
