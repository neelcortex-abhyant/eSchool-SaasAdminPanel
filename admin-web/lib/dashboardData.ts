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
  schools: RecentSchool[];
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

const PACKAGE_COLORS = ["#fbbf24", "#1f2937", "#f59e0b", "#ec4899", "#059669", "#7c3aed"];

type NamedRow = { id?: number; name?: string | null; status?: number | null };

function emptyPayload(message: string): DashboardPayload {
  return {
    source: "placeholder",
    counts: null,
    stats: [],
    revenue: [],
    packages: [],
    transactions: [],
    activity: [],
    schools: [],
    message,
  };
}

type PlatformCounts = {
  schools?: number;
  schools_active?: number;
  schools_inactive?: number;
  students?: number;
  school_admins?: number;
  super_admins?: number;
  plans?: number;
  plans_active?: number;
  packages_active?: number;
  subscriptions_active?: number;
  subscriptions_expired?: number;
};

type PlatformStats = { total_schools: number; active_schools: number; inactive_schools: number; total_students: number; total_teachers: number; active_subscriptions: number };

/** The platform's cards, from GET /super-admin/dashboard and /dashboard/stats (which adds teachers). */
export function platformCards(c: PlatformCounts, stats: Partial<PlatformStats>): StatCardData[] {
  const n = (value: number | undefined) => formatNumber(value ?? 0);
  const schools = stats.total_schools ?? c.schools;
  return [
    { id: "schools", title: "Schools", value: n(schools), meta: `${n(stats.active_schools ?? c.schools_active)} active · ${n(stats.inactive_schools ?? c.schools_inactive)} inactive`, tone: "blue", icon: "schools" },
    { id: "students", title: "Students", value: n(stats.total_students ?? c.students), meta: "Across all schools", tone: "green", icon: "students" },
    { id: "teachers", title: "Teachers", value: stats.total_teachers === undefined ? "—" : n(stats.total_teachers), meta: "Across all schools", tone: "purple", icon: "teachers" },
    { id: "subscriptions", title: "Active subscriptions", value: n(stats.active_subscriptions ?? c.subscriptions_active), meta: `${n(c.subscriptions_expired)} expired`, tone: "orange", icon: "payments" },
    { id: "plans", title: "Plans on offer", value: n(c.plans_active ?? c.packages_active), meta: `${n(c.plans)} in total`, tone: "teal", icon: "plans" },
    { id: "admins", title: "School admins", value: n(c.school_admins), meta: `${n(c.super_admins)} super admins`, tone: "rose", icon: "teachers" },
  ];
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export type RecentSchool = { id: number; name: string; code: string | null; plan: string | null; created_at: string | null; active: boolean };

/**
 * Platform dashboard from the super-admin routes: counts (/dashboard), schools registered per
 * month (/dashboard/registrations?year=), schools per plan (/dashboard/subscriptions), newest
 * audit activity and schools, and the latest payments. A part that fails is left empty.
 */
export async function loadDashboardPayload(year = new Date().getFullYear()): Promise<DashboardPayload> {
  const { api, apiErrorMessage } = await import("@/lib/api");
  const { loadPayments, paymentDate } = await import("@/lib/payments");
  try {
    const [dashboard, platform, registrations, distribution, activities, schools, payments] = await Promise.all([
      api<Partial<DashboardCounts> & PlatformCounts & { detail?: string }>("/super-admin/dashboard"),
      api<Partial<PlatformStats>>("/super-admin/dashboard/stats"),
      api<{ months?: { month: number; count: number }[] }>(`/super-admin/dashboard/registrations?year=${year}`),
      api<{ by_plan?: { package_id: number; plan_name: string | null; school_count: number }[]; schools_without_active_subscription?: number }>("/super-admin/dashboard/subscriptions"),
      api<{ items?: { id: number; title: string; description: string; created_at: string }[] }>("/super-admin/dashboard/recent-activities?limit=8"),
      api<{ items?: { id: number; name: string; code: string | null; plan_name: string | null; created_at: string | null; status: number }[] }>("/super-admin/dashboard/recent-schools?limit=6"),
      loadPayments({ page: 1, pageSize: 6, sort: "-created_at" }),
    ]);
    if (!dashboard.ok) {
      return emptyPayload(
        dashboard.status === 403
          ? "This account cannot open the platform dashboard. Sign in with a super admin account."
          : apiErrorMessage(dashboard.data, "Unable to load dashboard data. Try again."),
      );
    }

    const counts: DashboardCounts = {
      ...EMPTY_COUNTS,
      ...dashboard.data,
      packages: dashboard.data.packages_active ?? dashboard.data.packages ?? 0,
    };
    const byMonth = new Map((registrations.ok ? registrations.data.months ?? [] : []).map((row) => [row.month, row.count]));
    const plans = distribution.ok ? (distribution.data.by_plan ?? []).filter((row) => row.school_count > 0) : [];
    const without = distribution.ok ? distribution.data.schools_without_active_subscription ?? 0 : 0;
    const schoolsTotal = plans.reduce((sum, row) => sum + row.school_count, 0) + without;
    // Shares of all schools, so the centre figure is how many have an active plan.
    const slices: PackageSlice[] = schoolsTotal
      ? plans.map((row, index) => ({
          label: row.plan_name || `Plan ${row.package_id}`,
          value: Math.round((row.school_count / schoolsTotal) * 1000) / 10,
          color: PACKAGE_COLORS[index % PACKAGE_COLORS.length],
        }))
      : [];

    return {
      source: "api",
      counts,
      stats: platformCards(dashboard.data, platform.ok ? platform.data : {}),
      revenue: registrations.ok ? MONTHS.map((label, index) => ({ month: label, value: byMonth.get(index + 1) ?? 0 })) : [],
      packages: slices,
      transactions: payments.ok
        ? payments.data.items.map((row) => ({
            id: row.id,
            school: row.school_name,
            plan: row.plan_name,
            amount: `${row.currency === "INR" ? "₹" : `${row.currency} `}${row.amount.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`,
            status: ({ successful: "Paid", pending: "Pending", failed: "Failed", refunded: "Refunded" } as const)[row.status] ?? "Pending",
            date: paymentDate(row),
          }))
        : [],
      activity: activities.ok
        ? (activities.data.items ?? []).map((row) => ({ id: String(row.id), title: row.title, description: row.description, time: formatWhen(row.created_at) }))
        : [],
      schools: schools.ok
        ? (schools.data.items ?? []).map((row) => ({ id: row.id, name: row.name, code: row.code, plan: row.plan_name, created_at: row.created_at, active: row.status === 1 }))
        : [],
    };
  } catch {
    return emptyPayload("Unable to load dashboard data. Try again.");
  }
}

function formatWhen(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}
