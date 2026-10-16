import { api, type ApiResult } from "@/lib/api";

export type Plan = {
  id: number;
  name: string | null;
  description: string | null;
  status: number;
  monthly_price: number;
  yearly_price: number;
  student_limit: number | null;
  staff_limit: number | null;
};

export type PlanList = {
  items: Plan[];
  total: number;
  page: number;
  page_size: number;
};

export type Subscription = {
  id: number;
  school_id: number;
  package_id: number;
  status: number;
  start_date: string;
  end_date: string;
  cycle: string;
  auto_renew: number;
  agreed_price?: number | null;
  school_name?: string | null;
  plan_name?: string | null;
};

export type SubscriptionList = {
  items: Subscription[];
  total: number;
  page: number;
  page_size: number;
};

export type Bill = {
  id: number;
  amount: number;
  status: number;
  period_start: string;
  period_end: string;
  due_date: string | null;
  description: string | null;
};

export const PLAN_STATUS: Record<number, string> = { 0: "Inactive", 1: "Active" };
export const SUBSCRIPTION_STATUS: Record<number, string> = {
  0: "Inactive",
  1: "Active",
  2: "Expired",
  3: "Cancelled",
};

export function planStatusLabel(status: number): string {
  return PLAN_STATUS[status] || "Unknown";
}

export function subscriptionStatusLabel(status: number): string {
  return SUBSCRIPTION_STATUS[status] || "Unknown";
}

export function cycleLabel(cycle: string): string {
  if (cycle === "yearly") return "Yearly";
  if (cycle === "monthly") return "Monthly";
  return cycle;
}

export function limitLabel(value: number | null | undefined): string {
  return value == null ? "Unlimited" : String(value);
}

export function money(amount: number, currency = "INR"): string {
  const formatted = Number(amount || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${currency} ${formatted}`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function remainingDays(endDate: string): number {
  const end = new Date(`${endDate.slice(0, 10)}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((end.getTime() - today.getTime()) / 86400000);
}

export function addCycle(isoDate: string, cycle: "monthly" | "yearly"): string {
  const [year, month, day] = isoDate.slice(0, 10).split("-").map(Number);
  if (cycle === "yearly") {
    const nextYear = year + 1;
    const leap = nextYear % 4 === 0 && (nextYear % 100 !== 0 || nextYear % 400 === 0);
    const nextDay = month === 2 && day === 29 && !leap ? 28 : day;
    return iso(nextYear, month, nextDay);
  }
  let nextMonth = month + 1;
  let nextYear = year;
  if (nextMonth > 12) {
    nextMonth = 1;
    nextYear += 1;
  }
  const lastDay = new Date(Date.UTC(nextYear, nextMonth, 0)).getUTCDate();
  return iso(nextYear, nextMonth, Math.min(day, lastDay));
}

function iso(year: number, month: number, day: number): string {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function renewedPeriod(endDate: string, cycle: "monthly" | "yearly"): { start: string; end: string } {
  const now = new Date();
  const today = iso(now.getUTCFullYear(), now.getUTCMonth() + 1, now.getUTCDate());
  const currentEnd = endDate.slice(0, 10);
  const start = currentEnd >= today ? addDays(currentEnd, 1) : today;
  return { start, end: addCycle(start, cycle) };
}

function addDays(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.slice(0, 10).split("-").map(Number);
  const next = new Date(Date.UTC(year, month - 1, day + days));
  return iso(next.getUTCFullYear(), next.getUTCMonth() + 1, next.getUTCDate());
}

export function todayIso(): string {
  const now = new Date();
  return iso(now.getFullYear(), now.getMonth() + 1, now.getDate());
}

export function accessError(status: number, fallback: string): string {
  if (status === 401) return "Sign in again to manage subscriptions.";
  if (status === 403) return "This account cannot manage subscriptions. Sign in with a super admin account.";
  return fallback;
}

export function loadPlans(query: { page?: number; pageSize?: number; name?: string; status?: string }): Promise<ApiResult<PlanList>> {
  const params = new URLSearchParams({
    page: String(query.page ?? 1),
    page_size: String(query.pageSize ?? 20),
  });
  if (query.name) params.set("name", query.name);
  if (query.status === "0" || query.status === "1") params.set("status", query.status);
  return api<PlanList>(`/super-admin/plans?${params.toString()}`);
}

export function loadSubscriptionCatalog(query: {
  page?: number;
  pageSize?: number;
  q?: string;
  packageId?: string;
  status?: string;
  sort?: "end_date" | "-end_date";
}): Promise<ApiResult<SubscriptionList>> {
  const params = new URLSearchParams({
    page: String(query.page ?? 1),
    page_size: String(query.pageSize ?? 20),
    sort: query.sort ?? "-end_date",
  });
  if (query.q) params.set("q", query.q);
  if (query.packageId) params.set("package_id", query.packageId);
  if (query.status !== undefined && query.status !== "") params.set("status", query.status);
  return api<SubscriptionList>(`/super-admin/subscriptions?${params.toString()}`);
}
