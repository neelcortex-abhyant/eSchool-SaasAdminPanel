/**
 * Dashboard data layer.
 * Prefer live `/api/admin/dashboard` when session allows; otherwise use
 * clearly marked placeholder analytics so the UI remains usable.
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

/** Placeholder analytics — not production billing data. */
function placeholderAnalytics(counts: DashboardCounts | null): Omit<DashboardPayload, "source" | "counts" | "stats" | "message"> {
  const schools = counts?.schools ?? 3;
  return {
    revenue: [
      { month: "Jan", value: 12 },
      { month: "Feb", value: 18 },
      { month: "Mar", value: 14 },
      { month: "Apr", value: 22 },
      { month: "May", value: 28 },
      { month: "Jun", value: 24 },
      { month: "Jul", value: 31 },
      { month: "Aug", value: 27 },
      { month: "Sep", value: 35 },
      { month: "Oct", value: 30 },
      { month: "Nov", value: 38 },
      { month: "Dec", value: 42 },
    ],
    packages: [
      { label: "Basic", value: 37.5, color: "#22c55e" },
      { label: "Standard", value: 12.5, color: "#f59e0b" },
      { label: "Pro", value: 25, color: "#2563eb" },
      { label: "Premium", value: 25, color: "#ec4899" },
    ],
    transactions: [
      {
        id: "TX-1042",
        school: "North Campus",
        plan: "Pro",
        amount: "₹12,500",
        status: "Paid" as const,
        date: "2026-10-05",
      },
      {
        id: "TX-1041",
        school: "Riverdale High",
        plan: "Basic",
        amount: "₹4,800",
        status: "Pending" as const,
        date: "2026-10-04",
      },
      {
        id: "TX-1038",
        school: "Green Valley",
        plan: "Premium",
        amount: "₹18,000",
        status: "Paid" as const,
        date: "2026-10-02",
      },
      {
        id: "TX-1035",
        school: "City Academy",
        plan: "Standard",
        amount: "₹7,200",
        status: "Failed" as const,
        date: "2026-09-28",
      },
    ].slice(0, Math.max(1, schools)),
    activity: [
      {
        id: "a1",
        title: "New school registered",
        description: "Awaiting package assignment",
        time: "2 minutes ago",
      },
      {
        id: "a2",
        title: "Payment received",
        description: "Pro plan renewal",
        time: "15 minutes ago",
      },
      {
        id: "a3",
        title: "Student roster updated",
        description: "Bulk import completed",
        time: "1 hour ago",
      },
      {
        id: "a4",
        title: "Subscription upgraded",
        description: "Basic → Pro",
        time: "3 hours ago",
      },
    ],
  };
}

export async function loadDashboardPayload(): Promise<DashboardPayload> {
  try {
    const response = await fetch("/api/admin/dashboard", {
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    const payload = (await response.json().catch(() => ({}))) as {
      error?: boolean;
      message?: string;
      data?: Partial<DashboardCounts>;
    };

    if (response.ok && !payload.error && payload.data) {
      const counts: DashboardCounts = { ...EMPTY_COUNTS, ...payload.data };
      const analytics = placeholderAnalytics(counts);
      return {
        source: "api",
        counts,
        stats: statsFromCounts(counts),
        ...analytics,
        message:
          "Counts from /api/admin/dashboard. Chart/transaction samples are placeholders until billing APIs exist.",
      };
    }

    const analytics = placeholderAnalytics(null);
    return {
      source: "placeholder",
      counts: null,
      stats: statsFromCounts(EMPTY_COUNTS).map((s, i) => ({
        ...s,
        value: ["125", "4,850", "320", "87", "64", "24"][i] ?? s.value,
        meta: ["+0 this month", "↑ 12.5% this month", "Active roster", "14 addons available", "Published", "Awaiting review"][i] ?? s.meta,
      })),
      ...analytics,
      message:
        "Live dashboard counts need /api/admin session. Showing placeholder analytics for UI preview.",
    };
  } catch {
    const analytics = placeholderAnalytics(null);
    return {
      source: "placeholder",
      counts: null,
      stats: statsFromCounts(EMPTY_COUNTS).map((s, i) => ({
        ...s,
        value: ["125", "4,850", "320", "87", "64", "24"][i] ?? s.value,
      })),
      ...analytics,
      message: "Unable to reach dashboard API. Showing placeholder data.",
    };
  }
}
