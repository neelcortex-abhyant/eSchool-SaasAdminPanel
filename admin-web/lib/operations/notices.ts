/**
 * Announcements and notifications.
 * The server keeps announcements (title, description, session) and notifications (title, body)
 * at GET/POST /school-admin/announcements and /school-admin/notifications.
 * Live "notices" (contract, see backend/docs/OPERATIONS_MODULES_API_CONTRACT.md) adds audience,
 * publish_at and status on announcements, PATCH/DELETE /announcements/{id}, and audience plus
 * delivery counts on notifications.
 * Sample: the server still saves every published announcement and sent notification; the extra
 * details (audience, publish date, drafts, delivery counts) are kept in this browser.
 */
import { listRows, staffDirectory } from "@/lib/extras/api";
import { isOperationsLive } from "@/lib/operations/mode";
import type { Announcement, AnnouncementInput, Audience, DeliveryStatus, NoticeStatus, NotificationRecord } from "@/lib/operations/types";
import { peopleService } from "@/lib/people";
import { invalid, missing } from "@/lib/ops/store";
import { num, optStr, send, str, type Raw } from "@/lib/teaching/client";

const META_KEY = "operations-notices-v1";

type Meta = {
  announcements: Record<string, { audience: Audience[]; publish_at: string | null }>;
  drafts: (Omit<Announcement, "status"> & { status: "draft" })[];
  notifications: Record<string, { audience: Audience[]; recipients: number; delivered: number; failed: number }>;
};

function readMeta(): Meta {
  try {
    const saved = JSON.parse(window.localStorage.getItem(META_KEY) || "null") as Meta | null;
    if (saved) return { announcements: saved.announcements ?? {}, drafts: saved.drafts ?? [], notifications: saved.notifications ?? {} };
  } catch {
    // Unreadable: start fresh.
  }
  return { announcements: {}, drafts: [], notifications: {} };
}

function writeMeta(meta: Meta) {
  try {
    window.localStorage.setItem(META_KEY, JSON.stringify(meta));
  } catch {
    // Storage blocked: details last until reload.
  }
}

const live = () => isOperationsLive("notices");

function audienceOf(value: unknown): Audience[] {
  const list = Array.isArray(value) ? value.map(String) : typeof value === "string" && value ? value.split(",") : [];
  const valid = list.filter((item): item is Audience => ["all", "students", "parents", "teachers", "staff"].includes(item));
  return valid.length ? valid : ["all"];
}

/** Published, or scheduled when the publish time is still ahead. */
export function noticeStatus(publishAt: string | null, now = Date.now()): NoticeStatus {
  return publishAt && new Date(publishAt).getTime() > now ? "scheduled" : "published";
}

export function announcementProblems(input: AnnouncementInput): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!input.title.trim()) errors.title = "Enter a title.";
  else if (input.title.trim().length > 255) errors.title = "Keep the title under 255 characters.";
  if (!input.description.trim() && !input.draft) errors.description = "Write the announcement.";
  if (!input.session_year_id) errors.session_year_id = "Choose the academic session.";
  if (!input.audience.length) errors.audience = "Choose who it's for.";
  if (input.publish_at && Number.isNaN(new Date(input.publish_at).getTime())) errors.publish_at = "Choose a valid date and time.";
  return errors;
}

export async function listAnnouncements(): Promise<Announcement[]> {
  const rows = await listRows("/announcements");
  const meta = readMeta();
  const published = rows.map((row): Announcement => {
    const extra = meta.announcements[String(num(row.id))];
    const audience = live() ? audienceOf(row.audience) : extra?.audience ?? ["all"];
    const publishAt = live() ? optStr(row.publish_at) : extra?.publish_at ?? null;
    return {
      id: num(row.id),
      title: str(row.title ?? row.name),
      description: str(row.description),
      session_year_id: num(row.session_year_id) || null,
      audience,
      publish_at: publishAt,
      status: live() && optStr(row.status) ? (str(row.status) as NoticeStatus) : noticeStatus(publishAt),
      created_at: optStr(row.created_at),
    };
  });
  const drafts = live() ? [] : meta.drafts;
  return [...drafts, ...published].sort((a, b) => (b.publish_at ?? b.created_at ?? "").localeCompare(a.publish_at ?? a.created_at ?? ""));
}

/** Saves an announcement. A draft stays private until it's published; publishing sends it to the server. */
export async function saveAnnouncement(input: AnnouncementInput, id?: number): Promise<void> {
  const problems = announcementProblems(input);
  if (Object.keys(problems).length) invalid(problems);
  const body = { title: input.title.trim(), description: input.description.trim(), session_year_id: input.session_year_id };
  if (live()) {
    const full = { ...body, audience: input.audience, publish_at: input.publish_at, status: input.draft ? "draft" : noticeStatus(input.publish_at) };
    if (id) await send("PATCH", `/school-admin/announcements/${id}`, full, "Unable to save the announcement.");
    else await send("POST", "/school-admin/announcements", full, "Unable to post the announcement.");
    return;
  }
  const meta = readMeta();
  if (input.draft) {
    if (id && id > 0) invalid({ title: "A published announcement can't go back to draft." });
    const draft = { id: id && id < 0 ? id : -Date.now(), title: body.title, description: body.description, session_year_id: body.session_year_id, audience: input.audience, publish_at: input.publish_at, status: "draft" as const, created_at: new Date().toISOString() };
    meta.drafts = [draft, ...meta.drafts.filter((row) => row.id !== draft.id)];
    writeMeta(meta);
    return;
  }
  if (id && id > 0) {
    // The server can't edit a posted announcement yet; only its audience and date can change here.
    meta.announcements[String(id)] = { audience: input.audience, publish_at: input.publish_at };
    writeMeta(meta);
    return;
  }
  const row = await send("POST", "/school-admin/announcements", body, "Unable to post the announcement.");
  meta.announcements[String(num(row.id))] = { audience: input.audience, publish_at: input.publish_at };
  meta.drafts = meta.drafts.filter((item) => item.id !== id);
  writeMeta(meta);
}

export async function deleteAnnouncement(id: number): Promise<void> {
  if (live()) {
    await send("DELETE", `/school-admin/announcements/${id}`, undefined, "Unable to delete the announcement.");
    return;
  }
  const meta = readMeta();
  if (id > 0) invalid({ title: "The server can't delete a posted announcement yet." });
  if (!meta.drafts.some((row) => row.id === id)) missing("Draft");
  meta.drafts = meta.drafts.filter((row) => row.id !== id);
  writeMeta(meta);
}

/** Can this announcement be edited or deleted with today's server? */
export function canChange(row: Announcement): { edit: boolean; remove: boolean } {
  if (live()) return { edit: true, remove: true };
  return { edit: true, remove: row.id < 0 };
}

// ---------- notifications ----------

export function deliveryOf(recipients: number, delivered: number, failed: number): DeliveryStatus {
  if (!recipients) return "queued";
  if (failed >= recipients) return "failed";
  if (failed > 0 || delivered < recipients) return "partial";
  return "sent";
}

/** How many people an audience reaches, from the school's people lists. */
export async function audienceSize(audience: Audience[]): Promise<number> {
  const want = new Set(audience.includes("all") ? ["students", "parents", "teachers", "staff"] : audience);
  const [students, parents, people] = await Promise.all([
    want.has("students") ? peopleService("students").listStudents({ pageSize: 1, status: "1" }).then((page) => page.total).catch(() => 0) : 0,
    want.has("parents") ? peopleService("parents").listParents({ pageSize: 1 }).then((page) => page.total).catch(() => 0) : 0,
    want.has("teachers") || want.has("staff") ? staffDirectory().catch(() => []) : [],
  ]);
  const teachers = Array.isArray(people) ? people.filter((row) => row.kind === "teacher").length : 0;
  const staff = Array.isArray(people) ? people.filter((row) => row.kind === "staff").length : 0;
  return students + parents + (want.has("teachers") ? teachers : 0) + (want.has("staff") ? staff : 0);
}

export async function listNotifications(): Promise<NotificationRecord[]> {
  const rows = await listRows("/notifications");
  const meta = readMeta();
  return rows
    .map((row): NotificationRecord => {
      const extra = meta.notifications[String(num(row.id))];
      const recipients = live() ? num(row.recipients) : extra?.recipients ?? 0;
      const delivered = live() ? num(row.delivered) : extra?.delivered ?? 0;
      const failed = live() ? num(row.failed) : extra?.failed ?? 0;
      return {
        id: num(row.id),
        title: str(row.title),
        body: str(row.body),
        audience: live() ? audienceOf(row.audience) : extra?.audience ?? ["all"],
        created_at: optStr(row.created_at),
        delivery: live() && optStr(row.delivery) ? (str(row.delivery) as DeliveryStatus) : extra ? deliveryOf(recipients, delivered, failed) : num(row.status) === 1 ? "sent" : "queued",
        recipients,
        delivered,
        failed,
        failure_reason: live() ? optStr(row.failure_reason) : failed ? "Some people have no app sign-in or notifications are turned off." : null,
      };
    })
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
}

export function notificationProblems(input: { title: string; body: string; audience: Audience[] }): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!input.title.trim()) errors.title = "Enter a title.";
  if (!input.body.trim()) errors.body = "Write the message.";
  if (!input.audience.length) errors.audience = "Choose who gets it.";
  return errors;
}

export async function sendNotification(input: { title: string; body: string; audience: Audience[] }): Promise<void> {
  const problems = notificationProblems(input);
  if (Object.keys(problems).length) invalid(problems);
  const body: Raw = { title: input.title.trim(), body: input.body.trim(), status: 1 };
  if (live()) {
    await send("POST", "/school-admin/notifications", { ...body, audience: input.audience }, "Unable to send the notification.");
    return;
  }
  const row = await send("POST", "/school-admin/notifications", body, "Unable to send the notification.");
  // Sample delivery figures: everyone in the audience, a few without the app.
  const recipients = await audienceSize(input.audience);
  const failed = recipients ? Math.min(recipients, Math.floor(recipients * 0.03)) : 0;
  const meta = readMeta();
  meta.notifications[String(num(row.id))] = { audience: input.audience, recipients, delivered: recipients - failed, failed };
  writeMeta(meta);
}

/** Notifications matching a search and dates. */
export function filterNotifications(rows: NotificationRecord[], filter: { q: string; from: string; to: string; delivery: string }): NotificationRecord[] {
  const needle = filter.q.trim().toLowerCase();
  return rows.filter((row) => {
    const day = (row.created_at ?? "").slice(0, 10);
    return (!needle || `${row.title} ${row.body}`.toLowerCase().includes(needle)) && (!filter.from || day >= filter.from) && (!filter.to || day <= filter.to) && (!filter.delivery || row.delivery === filter.delivery);
  });
}
