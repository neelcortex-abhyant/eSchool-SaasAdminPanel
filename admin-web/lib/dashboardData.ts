/**
 * Dashboard data layer.
 * Live counts from `/api/admin/dashboard`. Fee rows and announcements fill the lower panels.
 */

export type DashboardCounts = {
  students: number;
  classes: number;
  subjects: number;
  attendances: number;
  exams: number;
  fees: number;
  announcements: number;
  leaves: number;
  expenses: number;
  schools: number;
  packages: number;
};

export type StatCardData = {
  id: string;
  title: string;
  value: string;
  meta: string;
  tone: "blue" | "green" | "purple" | "orange" | "teal" | "rose";
  icon: "schools" | "students" | "teachers" | "revenue" | "plans" | "payments";
};

export type MonthPoint = { month: string; value: number };

export type PackageSlice = { label: string; value: number; color: string };

export type TransactionRow = {
  id: string;
  school: string;
  plan: string;
  amount: string;
  status: "Paid" | "Pending" | "Failed" | "Refunded";
  date: string;
};

export type ActivityItem = {
  id: string;
  title: string;
  description: string;
  time: string;
};

export type DashboardPayload = {
  source: "api" | "placeholder";
  counts: DashboardCounts | null;
  stats: StatCardData[];
  revenue: MonthPoint[];
  packages: PackageSlice[];
  transactions: TransactionRow[];
  activity: ActivityItem[];
  message?: string;
};

const EMPTY_COUNTS: DashboardCounts = {
  students: 0,
  classes: 0,
  subjects: 0,
  attendances: 0,
  exams: 0,
  fees: 0,
  announcements: 0,
  leaves: 0,
  expenses: 0,
  schools: 0,
  packages: 0,
};

function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-IN").format(n);
}

function statsFromCounts(c: DashboardCounts): StatCardData[] {
  return [
    {
      id: "schools",
      title: "Total Schools",
      value: formatNumber(c.schools),
      meta: "Across the platform",
      tone: "blue",
      icon: "schools",
    },
    {
      id: "students",
      title: "Active Students",
      value: formatNumber(c.students),
      meta: "Scoped to current session",
      tone: "green",
      icon: "students",
    },
    {
      id: "classes",
      title: "Classes",
      value: formatNumber(c.classes),
      meta: `${formatNumber(c.subjects)} subjects`,
      tone: "purple",
      icon: "teachers",
    },
    {
      id: "packages",
      title: "Active Packages",
      value: formatNumber(c.packages),
      meta: `${formatNumber(c.fees)} fee plans`,
      tone: "orange",
      icon: "plans",
    },
    {
      id: "exams",
      title: "Exams",
      value: formatNumber(c.exams),
      meta: `${formatNumber(c.attendances)} attendance rows`,
      tone: "teal",
      icon: "revenue",
    },
    {
      id: "expenses",
      title: "Expenses logged",
      value: formatNumber(c.expenses),
      meta: `${formatNumber(c.leaves)} leave requests`,
      tone: "rose",
      icon: "payments",
    },
  ];
}

const PACKAGE_COLORS = ["#3dbb8a", "#2f5bff", "#f59e0b", "#ec4899", "#0d9488", "#7c3aed"];

type NamedRow = { id?: number; name?: string | null; status?: number | null };
type FeeRow = {
  id?: number;
  name?: string | null;
  due_charges?: number | null;
  due_date?: string | null;
  school_id?: number | null;
};
type NoticeRow = { id?: number; title?: string | null; description?: string | null };

function emptyPayload(message: string): DashboardPayload {
  return {
    source: "placeholder",
    counts: null,
    stats: [],
    revenue: [],
    packages: [],
    transactions: [],
    activity: [],
    message,
  };
}

export async function loadDashboardPayload(): Promise<DashboardPayload> {
  const { adminApi, adminErrorMessage } = await import("@/lib/adminApi");
  try {
    const dashboard = await adminApi<{ data?: Partial<DashboardCounts>; detail?: string; message?: string }>(
      "/dashboard",
    );
    if (!dashboard.ok || !dashboard.data.data) {
      return emptyPayload(adminErrorMessage(dashboard.data, "Unable to load dashboard data. Try again."));
    }

    const counts: DashboardCounts = { ...EMPTY_COUNTS, ...dashboard.data.data };
    const [packages, fees, notices] = await Promise.all([
      adminApi<{ data?: NamedRow[] }>("/packages"),
      adminApi<{ data?: FeeRow[] }>("/fees"),
      adminApi<{ data?: NoticeRow[] }>("/announcements"),
    ]);

    const packageRows = packages.ok ? packages.data.data || [] : [];
    const share = packageRows.length ? 100 / packageRows.length : 0;
    const slices: PackageSlice[] = packageRows.map((row, index) => ({
      label: row.name || `Package ${row.id ?? index + 1}`,
      value: Math.round(share * 10) / 10,
      color: PACKAGE_COLORS[index % PACKAGE_COLORS.length],
    }));

    const transactions: TransactionRow[] = (fees.ok ? fees.data.data || [] : []).slice(0, 8).map((fee) => ({
      id: `FEE-${fee.id ?? "—"}`,
      school: fee.school_id == null ? "—" : `School ${fee.school_id}`,
      plan: fee.name || "Fee",
      amount: fee.due_charges == null ? "—" : String(fee.due_charges),
      status: "Pending",
      date: fee.due_date || "—",
    }));

    const activity: ActivityItem[] = (notices.ok ? notices.data.data || [] : []).slice(0, 6).map((notice) => ({
      id: String(notice.id ?? notice.title),
      title: notice.title || "Announcement",
      description: notice.description || "School announcement",
      time: "Announcement",
    }));

    return {
      source: "api",
      counts,
      stats: statsFromCounts(counts),
      revenue: [],
      packages: slices,
      transactions,
      activity,
    };
  } catch {
    return emptyPayload("Unable to load dashboard data. Try again.");
  }
}
