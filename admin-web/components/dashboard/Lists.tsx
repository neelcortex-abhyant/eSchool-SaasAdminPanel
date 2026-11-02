import Link from "next/link";
import type { ActivityItem, RecentSchool, TransactionRow } from "@/lib/dashboardData";
import {
  IconBell,
  IconBuilding,
  IconChart,
  IconPackage,
  IconPlus,
  IconTeacher,
  IconUsers,
} from "@/lib/icons";

function statusClass(status: TransactionRow["status"]) {
  return status.toLowerCase();
}

export function RecentTransactions({ rows }: { rows: TransactionRow[] }) {
  if (!rows.length) {
    return <div className="empty-state">No payments yet</div>;
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>School</th>
            <th>Plan</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Date</th>
            <th>
              <span className="acad-sr">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td data-label="School">{row.school}</td>
              <td data-label="Plan">{row.plan}</td>
              <td data-label="Amount">{row.amount}</td>
              <td data-label="Status">
                <span className={`status-badge ${statusClass(row.status)}`}>{row.status}</span>
              </td>
              <td data-label="Date">{row.date}</td>
              <td>
                <Link href={`/payments/${encodeURIComponent(row.id)}`} className="link-btn">
                  View
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RecentSchools({ rows }: { rows: RecentSchool[] }) {
  if (!rows.length) {
    return <div className="empty-state">No schools yet</div>;
  }
  return (
    <div className="activity-list">
      {rows.map((row) => (
        <Link key={row.id} href={`/schools/${row.id}`} className="activity-item">
          <div className="activity-icon">
            <IconBuilding width={16} height={16} />
          </div>
          <div>
            <p className="activity-title">{row.name}</p>
            <p className="activity-meta">
              {[row.code, row.plan ?? "No plan", row.active ? "Active" : "Inactive", row.created_at ? new Date(row.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : null].filter(Boolean).join(" · ")}
            </p>
          </div>
        </Link>
      ))}
    </div>
  );
}

export function RecentActivity({ items }: { items: ActivityItem[] }) {
  if (!items.length) {
    return <div className="empty-state">No recent activity</div>;
  }

  return (
    <div className="activity-list">
      {items.map((item) => (
        <div key={item.id} className="activity-item">
          <div className="activity-icon">
            <IconBell width={16} height={16} />
          </div>
          <div>
            <p className="activity-title">{item.title}</p>
            <p className="activity-meta">
              {item.description} · {item.time}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

export function QuickActions() {
  const actions = [
    { href: "/schools/new", label: "Add School", icon: IconBuilding },
    { href: "/packages", label: "Create Plan", icon: IconPackage },
    { href: "/addons", label: "Add Add-on", icon: IconUsers },
    { href: "/announcements", label: "Send Notice", icon: IconBell },
    { href: "/reports", label: "View Reports", icon: IconChart },
    { href: "/settings", label: "Settings", icon: IconTeacher },
  ] as const;

  return (
    <div className="quick-grid">
      {actions.map((action) => {
        const Icon = action.icon;
        return (
          <Link key={action.href + action.label} href={action.href} className="quick-action">
            <IconPlus width={16} height={16} style={{ position: "absolute", opacity: 0 }} />
            <Icon width={20} height={20} />
            <span>{action.label}</span>
          </Link>
        );
      })}
    </div>
  );
}
