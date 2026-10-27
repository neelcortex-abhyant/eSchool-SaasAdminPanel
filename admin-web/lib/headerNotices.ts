/**
 * What the header bell shows. School admins see their school's latest announcements and
 * notifications (/school-admin/announcements and /school-admin/notifications), newest first;
 * super admins see the platform notifications.
 */
import { api } from "@/lib/api";

export type HeaderNotice = {
  id: string;
  title: string;
  detail: string;
  /** ISO date-time, or "" when the server sends none. */
  date: string;
  href: string;
};

type Row = { id: number; title?: string; description?: string | null; body?: string | null; created_at?: string | null };
type List = { items?: Row[] };

export const NOTICE_LIMIT = 8;

/** Announcements and notifications together, newest first. */
export function mergeNotices(announcements: Row[], notifications: Row[], limit = NOTICE_LIMIT): HeaderNotice[] {
  const rows: HeaderNotice[] = [
    ...announcements.map((row) => ({ id: `announcement-${row.id}`, title: row.title || "Announcement", detail: row.description || row.body || "", date: row.created_at || "", href: "/school/announcement" })),
    ...notifications.map((row) => ({ id: `notification-${row.id}`, title: row.title || "Notification", detail: row.body || "", date: row.created_at || "", href: "/school/notification" })),
  ];
  return rows.sort((a, b) => b.date.localeCompare(a.date)).slice(0, limit);
}

export function unreadCount(notices: HeaderNotice[], seen: string[]): number {
  return notices.filter((item) => !seen.includes(item.id)).length;
}

/** "28 Oct" (this year) or "28 Oct 2025"; "" when there's no date. */
export function noticeDate(value: string, now = new Date()): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "short", ...(date.getFullYear() === now.getFullYear() ? {} : { year: "numeric" }) });
}

export type NoticeLoad = { notices: HeaderNotice[]; error: string };

export async function loadHeaderNotices(role: string | undefined): Promise<NoticeLoad> {
  const signIn = "Sign in again to view notifications.";
  if (role === "school_admin") {
    const query = `?page=1&page_size=${NOTICE_LIMIT}`;
    const [announcements, notifications] = await Promise.all([api<List>(`/school-admin/announcements${query}`), api<List>(`/school-admin/notifications${query}`)]);
    if (!announcements.ok && !notifications.ok) {
      return { notices: [], error: announcements.status === 401 ? signIn : "Notifications could not be loaded." };
    }
    return {
      notices: mergeNotices(announcements.ok ? announcements.data.items ?? [] : [], notifications.ok ? notifications.data.items ?? [] : []),
      error: "",
    };
  }
  const result = await api<List>(`/super-admin/notifications?status=1&page=1&page_size=${NOTICE_LIMIT}`);
  if (!result.ok) return { notices: [], error: result.status === 401 || result.status === 403 ? signIn : "Notifications could not be loaded." };
  return {
    notices: (result.data.items ?? []).map((row) => ({ id: `notification-${row.id}`, title: row.title || "Notification", detail: row.body || "", date: row.created_at || "", href: "/announcements" })),
    error: "",
  };
}
