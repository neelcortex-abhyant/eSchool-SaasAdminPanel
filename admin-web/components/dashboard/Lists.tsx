import Link from "next/link";
import type { ActivityItem, TransactionRow } from "@/lib/dashboardData";
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
    return <div className="empty-state">No fee records</div>;
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Fee</th>
            <th>Scope</th>
            <th>Name</th>
            <th>Due charges</th>
            <th>Status</th>
            <th>Due date</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td className="mono">{row.id}</td>
              <td>{row.school}</td>
              <td>{row.plan}</td>
              <td>{row.amount}</td>
              <td>
                <span className={`status-badge ${statusClass(row.status)}`}>{row.status}</span>
              </td>
              <td>{row.date}</td>
              <td>
                <Link href="/fees" className="link-btn">
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

export function RecentActivity({ items }: { items: ActivityItem[] }) {
  if (!items.length) {
    return <div className="empty-state">No announcements</div>;
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
    { href: "/schools", label: "Add School", icon: IconBuilding },
    { href: "/students", label: "Add Student", icon: IconUsers },
    { href: "/classes", label: "Add Class", icon: IconTeacher },
    { href: "/packages", label: "Create Package", icon: IconPackage },
    { href: "/announcements", label: "Send Notice", icon: IconBell },
    { href: "/fees", label: "Generate Report", icon: IconChart },
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
