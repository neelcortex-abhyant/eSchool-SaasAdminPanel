import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { invalidateApiCache } from "@/lib/api";
import { StaffLeavePage } from "@/components/operations/Leave";
import { EXTRA_PAGES } from "@/lib/extras/pages";
import type { ResourceConfig } from "@/lib/extras/types";
import { decideLeave, loadLeaves } from "@/lib/operations/leave";
import { liveMessaging } from "@/lib/operations/messaging";
import { canCancel, cancelNotification, listNotifications } from "@/lib/operations/notices";

afterEach(cleanup);

type Call = { url: string; method: string; body: unknown };
let calls: Call[] = [];

function respond(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** Answers by "METHOD /path" or "/path" (GET); lists are wrapped in a page. */
function serve(table: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const method = init.method ?? "GET";
      const body = typeof init.body === "string" ? JSON.parse(init.body) : init.body instanceof FormData ? "form" : undefined;
      calls.push({ url: String(url), method, body });
      const path = String(url).replace(/^.*\/api\/v1/, "").split("?")[0];
      const value = table[`${method} ${path}`] ?? (method === "GET" ? table[path] : undefined);
      if (value === undefined) return method === "GET" ? respond({ items: [], total: 0, page: 1, page_size: 50 }) : respond({ id: 77 });
      return respond(Array.isArray(value) ? { items: value, total: value.length, page: 1, page_size: 50 } : value);
    }),
  );
}

beforeEach(() => {
  calls = [];
  invalidateApiCache();
  window.localStorage.clear();
  window.localStorage.setItem("v1_access_token", "test-token");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const LEAVE_SERVER = {
  "/school-admin/me": { id: 1 },
  "/school-admin/leave-types": [{ id: 2, code: "SL", name: "Sick leave", days_per_year: 10, applies_to: "teacher", is_active: true }],
  "/school-admin/academics/leaves": [
    { id: 41, user_id: 31, student_id: null, reason: "Fever", leave_type: "Sick leave", from_date: "2026-11-02", to_date: "2026-11-03", status: 0 },
    { id: 42, user_id: 31, student_id: null, reason: "Trip", leave_type: "Sick leave", from_date: "2026-10-02", to_date: "2026-10-02", status: 3 },
  ],
  "/school-admin/staff": [{ id: 31, staff_id: 5, name: "Asha Rao", designation: "Clerk" }],
  "/school-admin/teachers": [],
};

describe("leave decisions (backend 0045)", () => {
  it("approves, rejects and cancels through the server's routes", async () => {
    serve({});
    await decideLeave(41, "reject");
    await decideLeave(41, "cancel");
    expect(calls.map((call) => `${call.method} ${call.url.replace(/^.*\/api\/v1/, "")}`)).toEqual(["POST /school-admin/academics/leaves/41/reject", "POST /school-admin/academics/leaves/41/cancel"]);
  });

  it("keeps cancelled leave as cancelled and offers no decision on it", async () => {
    serve(LEAVE_SERVER);
    expect((await loadLeaves([])).map((row) => [row.id, row.status])).toEqual([[41, 0], [42, 3]]);
    render(<StaffLeavePage />);
    // The page opens on pending leave; show everything.
    await screen.findAllByText("Asha Rao");
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "" } });
    const cancelled = (await screen.findByText("Cancelled", { selector: ".status-badge" })).closest("tr") as HTMLElement;
    expect(within(cancelled).queryByRole("button", { name: /approve|reject|cancel/i })).toBeNull();
    const pending = (await screen.findByText("Pending", { selector: ".status-badge" })).closest("tr") as HTMLElement;
    fireEvent.click(within(pending).getByRole("button", { name: "Cancel" }));
    await screen.findByText("Cancel this leave request?");
    fireEvent.click(screen.getByRole("button", { name: "Cancel leave" }));
    await waitFor(() => expect(calls.some((call) => call.method === "POST" && call.url.endsWith("/academics/leaves/41/cancel"))).toBe(true));
  });

  it("decides student leave with row actions and edits only pending leave", () => {
    const config = EXTRA_PAGES["student-leave"] as ResourceConfig;
    expect(config.fields.some((field) => field.key === "status")).toBe(false);
    expect(config.canEditRow?.({ id: 1, status: 0 })).toBe(true);
    expect(config.canEditRow?.({ id: 1, status: 1 })).toBe(false);
    const approve = config.rowActions?.find((action) => action.label === "Approve");
    expect(approve?.path({ id: 9 })).toBe("/academics/leaves/9/approve");
    expect(approve?.show({ id: 9, status: 2 })).toBe(false);
  });
});

describe("notifications (backend 0045)", () => {
  it("reads the cancelled status and cancels a queued notification", async () => {
    serve({
      "/school-admin/notifications": [
        { id: 5, title: "Fees", body: "Due", status: 1, delivery: "queued", audience: ["parents"], recipients: 0, delivered: 0, failed: 0, created_at: "2026-10-30T09:00:00" },
        { id: 6, title: "Trip", body: "Cancelled", status: 1, delivery: "cancelled", audience: ["all"], created_at: "2026-10-29T09:00:00" },
      ],
      "POST /school-admin/notifications/5/cancel": { id: 5, title: "Fees", body: "Due", status: 1, delivery: "cancelled", audience: ["parents"] },
    });
    const rows = await listNotifications();
    expect(rows.map((row) => [row.id, row.delivery, canCancel(row)])).toEqual([[5, "queued", true], [6, "cancelled", false]]);
    expect((await cancelNotification(5)).delivery).toBe("cancelled");
  });
});

describe("message attachments (backend 0045)", () => {
  it("uploads a file, sends it with the message and reads the download path back", async () => {
    const meta = { original_filename: "groups.pdf", content_type: "application/pdf", size_bytes: 2048, storage_key: "3/9/abc.pdf" };
    serve({
      "POST /school-admin/conversations/attachments/upload": meta,
      "POST /school-admin/conversations/4/messages": {
        id: 70,
        conversation_id: 4,
        sender: { user_id: 9, name: "School Admin", role: "school" },
        body: "See attached",
        attachments: [{ ...meta, name: "groups.pdf", size: 2048, download_path: "/api/v1/school-admin/messages/70/attachments?storage_key=3%2F9%2Fabc.pdf" }],
        sent_at: "2026-10-30T10:00:00",
      },
      "/school-admin/conversations/unread-count": { unread: 4, conversations: [] },
    });
    const uploaded = await liveMessaging.uploadAttachment(new File(["%PDF"], "groups.pdf", { type: "application/pdf" }));
    expect(uploaded).toEqual(meta);
    const sent = await liveMessaging.send(4, "See attached", [uploaded]);
    expect(calls.find((call) => call.url.endsWith("/conversations/4/messages"))?.body).toEqual({ body: "See attached", attachments: [meta] });
    expect(sent.attachments[0]).toMatchObject({ name: "groups.pdf", size: 2048, download_path: "/school-admin/messages/70/attachments?storage_key=3%2F9%2Fabc.pdf" });
    expect(await liveMessaging.unreadCount()).toBe(4);
  });
});

describe("super-admin dashboard routes", () => {
  it("fills the charts and lists from the dashboard routes", async () => {
    const { loadDashboardPayload } = await import("@/lib/dashboardData");
    serve({
      "/super-admin/dashboard": { schools: 12, schools_active: 10, schools_inactive: 2, students: 900, packages: 3, packages_active: 2, plans: 3, plans_active: 2, super_admins: 1, school_admins: 14, subscriptions_active: 6, subscriptions_expired: 1 },
      "/super-admin/dashboard/stats": { total_schools: 12, active_schools: 10, inactive_schools: 2, total_students: 900, total_teachers: 61, active_subscriptions: 6 },
      "/super-admin/dashboard/registrations": { year: 2026, total: 5, unscheduled: 0, months: [{ month: 3, count: 2 }, { month: 10, count: 3 }] },
      "/super-admin/dashboard/subscriptions": { by_plan: [{ package_id: 1, plan_name: "Basic", school_count: 6 }, { package_id: 2, plan_name: "Pro", school_count: 0 }], schools_with_active_subscription: 6, schools_without_active_subscription: 6 },
      "/super-admin/dashboard/recent-activities": { items: [{ id: 7, action: "school.create", entity_type: "school", entity_id: "4", school_id: 4, created_at: "2026-10-30T09:00:00", title: "School created", description: "Green Valley" }] },
      "/super-admin/dashboard/recent-schools": { items: [{ id: 4, name: "Green Valley", code: "GV", created_at: "2026-10-30T09:00:00", status: 1, installed: 1, package_id: 1, plan_name: "Basic" }], limit: 6 },
    });
    const payload = await loadDashboardPayload(2026);
    expect(calls.some((call) => call.url.includes("/super-admin/dashboard/registrations?year=2026"))).toBe(true);
    expect(payload.stats.map((card) => [card.title, card.value])).toEqual([
      ["Schools", "12"],
      ["Students", "900"],
      ["Teachers", "61"],
      ["Active subscriptions", "6"],
      ["Plans on offer", "2"],
      ["School admins", "14"],
    ]);
    expect(payload.revenue).toHaveLength(12);
    expect(payload.revenue[2]).toEqual({ month: "Mar", value: 2 });
    expect(payload.revenue[9]).toEqual({ month: "Oct", value: 3 });
    // Shares of all 12 schools; plans with no schools are left out.
    expect(payload.packages.map((slice) => [slice.label, slice.value])).toEqual([["Basic", 50]]);
    expect(payload.activity[0]).toMatchObject({ id: "7", title: "School created", description: "Green Valley" });
    expect(payload.schools).toEqual([{ id: 4, name: "Green Valley", code: "GV", plan: "Basic", created_at: "2026-10-30T09:00:00", active: true }]);
  });
});

describe("single trip and question bank", () => {
  it("reads one trip from its own route", async () => {
    const { liveTracking } = await import("@/lib/operations/tracking");
    serve({ "/school-admin/transport-trips/9": { id: 9, school_id: 1, route_id: 2, vehicle_id: 3, status: "scheduled", route_name: "North", registration_no: "KA 01" } });
    const trip = await liveTracking.trip(9);
    expect(trip.id).toBe(9);
    const tripCalls = calls.filter((call) => call.url.includes("/transport-trips"));
    expect(tripCalls.map((call) => call.url.replace(/^.*\/api\/v1/, "").split("?")[0])).toEqual(["/school-admin/transport-trips/9"]);
  });

  it("copies bank questions into an exam in one request on the server", async () => {
    vi.stubEnv("NEXT_PUBLIC_TEACHING_API_MODE", "live");
    vi.resetModules();
    const { copyBankQuestionsToExam } = await import("@/lib/teaching/exams");
    serve({ "POST /school-admin/online-assessments/5/questions/from-bank": { assessment_id: 5, copied_question_ids: [31, 32], count: 2 } });
    const question = { id: 11, question_text: "2 + 2?", topic: null, marks: 1, sort_order: 0, subject_name: null, choices: [] };
    expect(await copyBankQuestionsToExam(5, [question, { ...question, id: 12 }])).toEqual([]);
    expect(calls).toHaveLength(1);
    expect(calls[0].body).toEqual({ question_ids: [11, 12] });
    vi.unstubAllEnvs();
  });
});

describe("platform backups", () => {
  it("says plainly when a backup is a record rather than a copy", async () => {
    const { backupStatus } = await import("@/lib/backups");
    expect(backupStatus("metadata_only").label).toBe("Record only, not a database copy");
    expect(backupStatus("restored_requested").label).toBe("Restore requested");
    expect(backupStatus("something_new").label).toBe("something_new");
  });
});
