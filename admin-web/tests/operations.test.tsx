import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { invalidateApiCache } from "@/lib/api";
import { correctionProblems, workingDays } from "@/components/extras/StaffAttendance";
import { safeImage } from "@/components/extras/IdCard";
import { staffValues, studentValues } from "@/components/operations/Documents";
import { filterLeaves, StaffLeavePage } from "@/components/operations/Leave";
import { filterLocations } from "@/components/operations/Tracking";
import { toCsv } from "@/lib/operations/export";
import { balances, joinReason, leaveDays, leaveTypeProblems, splitReason, typesFromPolicy, DEFAULT_LEAVE_TYPES } from "@/lib/operations/leave";
import { filterConversations, messageProblem, mockMessaging, resetMessagingMock } from "@/lib/operations/messaging";
import { parseOperationsMode } from "@/lib/operations/mode";
import { announcementProblems, deliveryOf, filterNotifications, listAnnouncements, noticeStatus, saveAnnouncement } from "@/lib/operations/notices";
import { mockPayroll, monthWorkingDays, previewLine, resetPayrollMock, structureProblems, structureTotals } from "@/lib/operations/payroll";
import { ageLabel, boardingRate, freshness, mockTracking } from "@/lib/operations/tracking";
import type { Conversation, LeaveRequest, NotificationRecord, VehicleLocation } from "@/lib/operations/types";
import { resetOpsMock } from "@/lib/ops/store";

afterEach(cleanup);

type Call = { url: string; method: string; body: unknown };
let calls: Call[] = [];

function respond(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** GETs answered by exact path; other methods echo the body with an id. */
function serve(table: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const method = init.method ?? "GET";
      const body = typeof init.body === "string" ? JSON.parse(init.body) : undefined;
      calls.push({ url: String(url), method, body });
      const path = String(url).replace(/^.*\/api\/v1/, "").split("?")[0];
      if (method !== "GET") return respond({ id: 77, ...(body ?? {}) }, method === "POST" ? 201 : 200);
      const value = table[path];
      if (value === undefined) return respond({ items: [], total: 0, page: 1, page_size: 50 });
      return respond(Array.isArray(value) ? { items: value, total: value.length, page: 1, page_size: 50 } : value);
    }),
  );
}

beforeEach(() => {
  calls = [];
  invalidateApiCache();
  window.localStorage.clear();
  window.localStorage.setItem("v1_access_token", "test-token");
  resetOpsMock();
  resetPayrollMock();
  resetMessagingMock();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("operations mode flag", () => {
  it("uses the server for every feature by default and reads per-feature settings", () => {
    expect(parseOperationsMode(undefined)).toEqual({ tracking: "live", payroll: "live", messaging: "live", notices: "live" });
    expect(parseOperationsMode("mock").tracking).toBe("mock");
    expect(parseOperationsMode("live").payroll).toBe("live");
    expect(parseOperationsMode("tracking:live, payroll:mock")).toMatchObject({ tracking: "live", payroll: "mock", messaging: "live" });
  });
});

describe("module 1: bus tracking and transport attendance", () => {
  const now = Date.parse("2026-10-29T08:00:00Z");
  const at = (minutesAgo: number) => new Date(now - minutesAgo * 60_000).toISOString();

  it("marks locations live, stale or offline by age", () => {
    expect(freshness(at(1), now)).toBe("live");
    expect(freshness(at(10), now)).toBe("stale");
    expect(freshness(at(45), now)).toBe("offline");
    expect(ageLabel(at(65), now)).toBe("1 h 5 min ago");
  });

  it("filters buses by route, vehicle, trip status and freshness", () => {
    const base = { registration_no: "X", route_name: "R", driver_name: null, latitude: 0, longitude: 0, speed_kmph: null, heading: null };
    const rows: VehicleLocation[] = [
      { ...base, vehicle_id: 1, route_id: 1, trip_id: 1, trip_status: "active", recorded_at: at(1) },
      { ...base, vehicle_id: 2, route_id: 2, trip_id: null, trip_status: null, recorded_at: at(40) },
    ];
    expect(filterLocations(rows, { routeId: "1", vehicleId: "", status: "" }, now).map((row) => row.vehicle_id)).toEqual([1]);
    expect(filterLocations(rows, { routeId: "", vehicleId: "", status: "offline" }, now).map((row) => row.vehicle_id)).toEqual([2]);
    expect(filterLocations(rows, { routeId: "", vehicleId: "", status: "none" }, now).map((row) => row.vehicle_id)).toEqual([2]);
  });

  it("builds sample trips and boarding records from the school's vehicles and routes", async () => {
    const trips = await mockTracking.trips({ pageSize: 50 });
    expect(trips.total).toBeGreaterThan(0);
    const trip = trips.items.find((row) => row.status === "completed") ?? trips.items[0];
    expect(trip).toMatchObject({ registration_no: expect.any(String), driver_name: expect.any(String) });
    const riders = await mockTracking.attendance({ tripId: trip.id, pageSize: 50 });
    expect(riders.items.every((row) => row.trip_id === trip.id)).toBe(true);
    const locations = await mockTracking.locations();
    expect(locations.length).toBeGreaterThan(0);
    expect(locations.every((row) => Number.isFinite(row.latitude) && Number.isFinite(row.longitude))).toBe(true);
  });

  it("needs a reason to correct a boarding record and keeps the correction", async () => {
    const trips = await mockTracking.trips({ status: "completed", pageSize: 50 });
    const [record] = (await mockTracking.attendance({ tripId: trips.items[0].id, pageSize: 50 })).items;
    await expect(mockTracking.correct(record.id, "absent", " ")).rejects.toMatchObject({ status: 422 });
    const fixed = await mockTracking.correct(record.id, "absent", "Parent picked up at the gate");
    expect(fixed).toMatchObject({ status: "absent", corrected_by: "School admin", note: "Parent picked up at the gate" });
  });

  it("reads the server's trips and turns board/drop events into boarding records", async () => {
    const { tripFromServer, attendanceFromEvents } = await import("@/lib/operations/tracking");
    const context = {
      routes: [{ id: 2, name: "North", description: null, vehicle_id: 1, vehicle_label: null, capacity: 40, assigned_students: 3, status: 1 as const, stops: [{ id: 3, route_id: 2, name: "Gate", stop_order: 1, pickup_time: null, drop_time: null, landmark: null }] }],
      vehicles: [{ id: 1, registration_no: "KA01", vehicle_type: "other" as const, model: null, capacity: 40, driver_id: 5, driver_name: "Ravi", helper_id: null, helper_name: "Lata", status: 1 as const, assigned_students: 3 }],
      riders: [7, 8, 9].map((id) => ({ id, student_id: id, student_name: `S${id}`, admission_no: `A${id}`, class_name: "", section_name: "", route_id: 2, route_name: "North", stop_id: 3, stop_name: "Gate", direction: "both" as const, start_date: "", status: 1 as const })),
      people: [{ staff_id: 5, user_id: 31, name: "Ravi Kumar", designation: "Driver", kind: "staff" as const }],
    };
    const trip = tripFromServer({ id: 40, route_id: 2, vehicle_id: 1, driver_staff_id: 5, status: "in_progress", started_at: "2026-10-29T07:00:00", created_at: "2026-10-29T06:00:00" }, context);
    expect(trip).toMatchObject({ status: "active", route_name: "North", registration_no: "KA01", driver_name: "Ravi Kumar", helper_name: "Lata", expected: 3, direction: null });
    const rows = attendanceFromEvents(trip, [
      { student_id: 7, event_type: "board", stop_id: 3, recorded_at: "2026-10-29T07:10:00" },
      { student_id: 8, event_type: "board", recorded_at: "2026-10-29T07:12:00" },
      { student_id: 8, event_type: "drop", recorded_at: "2026-10-29T07:40:00" },
    ], context);
    expect(rows.map((row) => [row.student_id, row.status, row.stop_name])).toEqual([[7, "boarded", "Gate"], [8, "dropped", "Gate"], [9, "pending", "Gate"]]);
    expect(attendanceFromEvents({ ...trip, status: "completed" }, [], context)[0].status).toBe("absent");
  });

  it("works out boarding rates for reports", () => {
    expect(boardingRate([{ status: "boarded" }, { status: "dropped" }, { status: "absent" }, { status: "pending" }])).toBe(67);
    expect(boardingRate([])).toBe(0);
  });
});

describe("module 2: staff attendance and leave", () => {
  it("checks attendance corrections", () => {
    expect(correctionProblems({ status: "present", check_in: "09:00", check_out: "08:00" })).toEqual({ check_out: "Check-out must be after check-in." });
    expect(correctionProblems({ status: "absent", check_in: "09:00", check_out: "" })).toHaveProperty("status");
    expect(correctionProblems({ status: "late", check_in: "9:5", check_out: "" })).toHaveProperty("check_in");
    expect(correctionProblems({ status: "present", check_in: "08:45", check_out: "16:30" })).toEqual({});
  });

  it("counts working days without Sundays and holidays", () => {
    // 1–7 Nov 2026: Sunday the 1st, holiday on the 4th.
    expect(workingDays("2026-11-01", "2026-11-07", [{ holiday_date: "2026-11-04", end_date: null }])).toBe(5);
  });

  it("keeps the leave type in the reason and reads it back", () => {
    expect(joinReason("Sick leave", " Fever ")).toBe("Sick leave: Fever");
    expect(splitReason("Sick leave: Fever", DEFAULT_LEAVE_TYPES)).toEqual({ type: "Sick leave", reason: "Fever" });
    expect(splitReason("Note: not a type", DEFAULT_LEAVE_TYPES)).toEqual({ type: null, reason: "Note: not a type" });
    expect(leaveDays("2026-11-02", "2026-11-04")).toBe(3);
  });

  it("reads leave types from new and old settings and checks them", () => {
    expect(typesFromPolicy({ staff_casual_days: 8 })[0]).toMatchObject({ name: "Casual leave", days_per_year: 8 });
    expect(typesFromPolicy({ types: [{ name: "Study leave", days_per_year: 5 }] })).toEqual([{ key: "study_leave", name: "Study leave", days_per_year: 5, applies_to: "staff" }]);
    expect(leaveTypeProblems([{ key: "a", name: "A: b", days_per_year: 1, applies_to: "staff" }])).toHaveProperty("types.0");
  });

  it("works out balances from approved leave", () => {
    const leave = (id: number, type: string, status: 0 | 1 | 2, days: number): LeaveRequest => ({ id, user_id: 9, person_name: "Asha", kind: "staff", leave_type: type, reason: "", from_date: "2026-03-01", to_date: "2026-03-01", days, status });
    const rows = [leave(1, "Casual leave", 1, 2), leave(2, "Casual leave", 0, 1), leave(3, "Casual leave", 2, 4)];
    expect(balances(rows, 9, DEFAULT_LEAVE_TYPES, 2026)[0]).toMatchObject({ allowed: 12, used: 2, pending: 1, remaining: 10 });
    expect(filterLeaves(rows, { status: "0", userId: "", type: "", q: "", from: "", to: "" }).map((row) => row.id)).toEqual([2]);
  });

  it("approves a pending leave on the server after confirming", async () => {
    serve({
      "/school-admin/me": { id: 1 },
      "/school-admin/leave-types": [{ id: 2, code: "SL", name: "Sick leave", days_per_year: 10, applies_to: "staff", is_active: true }],
      "/school-admin/academics/leaves": [{ id: 41, user_id: 31, student_id: null, reason: "Fever", leave_type_id: 2, leave_type: "Sick leave", from_date: "2026-11-02", to_date: "2026-11-03", status: 0 }],
      "/school-admin/staff": [{ id: 31, staff_id: 5, name: "Asha Rao", designation: "Clerk" }],
      "/school-admin/teachers": [],
    });
    render(<StaffLeavePage />);
    const row = (await screen.findByRole("button", { name: "Asha Rao" })).closest("tr") as HTMLElement;
    expect(within(row).getByText("Sick leave")).toBeTruthy();
    fireEvent.click(within(row).getByRole("button", { name: "Approve" }));
    // The confirm dialog's button is the last "Approve" on the page.
    await screen.findByText("Approve this leave?");
    fireEvent.click(screen.getAllByRole("button", { name: "Approve" }).at(-1) as HTMLElement);
    await waitFor(() => expect(calls.some((call) => call.method === "PATCH")).toBe(true));
    const patch = calls.find((call) => call.method === "PATCH");
    expect(patch?.url).toMatch(/\/school-admin\/academics\/leaves\/41$/);
    expect(patch?.body).toEqual({ status: 1 });
  });
});

describe("module 3: payroll", () => {
  it("totals a structure and checks it", () => {
    const input = { name: "T", basic: 30000, allowances: [{ name: "HRA", amount: 8000 }], deductions: [{ name: "PF", amount: 3600 }] };
    expect(structureTotals(input)).toEqual({ allowances: 8000, deductions: 3600, gross: 38000, net: 34400 });
    expect(structureProblems({ ...input, deductions: [{ name: "PF", amount: 50000 }] })).toHaveProperty("deductions");
    expect(structureProblems({ ...input, allowances: [{ name: "HRA", amount: 1 }, { name: "hra", amount: 1 }] })).toHaveProperty("allowances.1");
  });

  it("deducts unpaid absence pro rata in the sample calculation", () => {
    const person = { staff_id: 5, user_id: 31, name: "Asha", designation: "Clerk", kind: "staff" as const, department: "Office" };
    const structure = { id: 1, name: "S", basic: 26000, allowances: [], deductions: [], gross: 26000, net: 26000, assigned: 1 };
    expect(previewLine(person, structure, 2, 26)).toMatchObject({ attendance_adjustment: 2000, paid_days: 24, net: 24000, eligible: true });
    expect(previewLine(person, null, 0, 26)).toMatchObject({ eligible: false, problem: "No salary structure assigned" });
    expect(monthWorkingDays("2026-11")).toBe(25);
  });

  it("processes a month once, and a retried request gets the same answer", async () => {
    serve({ "/school-admin/staff": [{ id: 31, staff_id: 5, name: "Asha Rao", designation: "Clerk", department: "Office" }], "/school-admin/teachers": [], "/school-admin/staff-attendance/reports": { items: [] } });
    await mockPayroll.assign([5], 2, "2026-10-01");
    const preview = await mockPayroll.preview("2026-10");
    expect(preview.lines[0]).toMatchObject({ eligible: true, structure_name: "Office staff" });
    const first = await mockPayroll.process("2026-10", "key-1");
    expect(first).toEqual({ processed: 1, failed: 0 });
    expect(await mockPayroll.process("2026-10", "key-1")).toEqual(first);
    await expect(mockPayroll.process("2026-10", "key-2")).rejects.toMatchObject({ status: 409 });
    const slips = await mockPayroll.payslips({ month: "2026-10" });
    expect(slips.items[0]).toMatchObject({ name: "Asha Rao", status: "processed", net: preview.lines[0].net });
  });
});

describe("module 4: announcements and notifications", () => {
  it("checks announcements and works out their status", () => {
    expect(announcementProblems({ title: "", description: "", session_year_id: 0, audience: [], publish_at: null, draft: false })).toEqual({ title: "Enter a title.", description: "Write the announcement.", session_year_id: "Choose the academic session.", audience: "Choose who it's for." });
    expect(noticeStatus("2999-01-01T00:00:00")).toBe("scheduled");
    expect(noticeStatus(null)).toBe("published");
  });

  it("saves drafts and publishes with audience and status on the server, and reads them back", async () => {
    serve({ "/school-admin/announcements": [{ id: 5, title: "Sports day", description: "Friday", session_year_id: 3, audience: ["parents"], publish_at: null, status: "draft", created_at: "2026-10-29T09:00:00" }] });
    await saveAnnouncement({ title: "Sports day", description: "Friday", session_year_id: 3, audience: ["parents"], publish_at: null, draft: true });
    expect(calls.find((call) => call.method === "POST")?.body).toEqual({ title: "Sports day", description: "Friday", session_year_id: 3, audience: ["parents"], publish_at: null, status: "draft" });
    const [draft] = await listAnnouncements();
    expect(draft).toMatchObject({ id: 5, status: "draft", audience: ["parents"] });
    await saveAnnouncement({ title: "Sports day", description: "Friday", session_year_id: 3, audience: ["parents"], publish_at: null, draft: false }, draft.id);
    const patch = calls.find((call) => call.method === "PATCH");
    expect(patch?.url).toMatch(/\/school-admin\/announcements\/5$/);
    expect(patch?.body).toMatchObject({ status: "published" });
  });

  it("summarises delivery and filters history", () => {
    expect(deliveryOf(10, 10, 0)).toBe("sent");
    expect(deliveryOf(10, 8, 2)).toBe("partial");
    expect(deliveryOf(3, 0, 3)).toBe("failed");
    const row = (id: number, title: string, day: string): NotificationRecord => ({ id, title, body: "", audience: ["all"], created_at: `${day}T10:00:00`, delivery: "sent", recipients: 0, delivered: 0, failed: 0, failure_reason: null });
    const rows = [row(1, "Fees due", "2026-10-01"), row(2, "Holiday", "2026-10-20")];
    expect(filterNotifications(rows, { q: "fee", from: "", to: "", delivery: "" }).map((item) => item.id)).toEqual([1]);
    expect(filterNotifications(rows, { q: "", from: "2026-10-10", to: "", delivery: "" }).map((item) => item.id)).toEqual([2]);
  });
});

describe("module 5: teacher–parent messages", () => {
  it("checks messages and filters conversations", () => {
    expect(messageProblem("  ")).toBe("Write a message.");
    expect(messageProblem("x".repeat(2001))).toMatch(/under 2000/);
    const conversation = (id: number, unread: number, flagged: boolean, at: string): Conversation => ({ id, subject: `S${id}`, student_id: id, student_name: `Student ${id}`, class_name: "5 A", teacher: { user_id: 1, name: "Neha", role: "teacher" }, parent: { user_id: 2, name: "Kiran", role: "parent" }, last_message: "", last_message_at: at, unread, flagged });
    const rows = [conversation(1, 0, false, "2026-10-01"), conversation(2, 3, true, "2026-10-02")];
    expect(filterConversations(rows, { unreadOnly: true }).map((row) => row.id)).toEqual([2]);
    expect(filterConversations(rows, { q: "student 1" }).map((row) => row.id)).toEqual([1]);
    expect(filterConversations(rows).map((row) => row.id)).toEqual([2, 1]);
  });

  it("sends, marks read and moderates in the sample inbox", async () => {
    const [first] = await mockMessaging.conversations();
    expect(first).toBeTruthy();
    await mockMessaging.send(first.id, "Thanks, the school has noted this.");
    const messages = await mockMessaging.messages(first.id);
    expect(messages[messages.length - 1]).toMatchObject({ body: "Thanks, the school has noted this.", sender: { role: "school_admin" } });
    await mockMessaging.hide(messages[0].id, true);
    expect((await mockMessaging.messages(first.id))[0].hidden).toBe(true);
    await mockMessaging.markRead(first.id);
    expect((await mockMessaging.conversations()).find((row) => row.id === first.id)?.unread).toBe(0);
  });
});

describe("module 6: certificates and ID cards", () => {
  it("fills placeholders for students and staff", () => {
    expect(studentValues({ name: "Diya", admission_no: "A1", class_name: "5", section_name: "A", roll_number: 12, guardian_name: "Kiran", session_name: "2026-27" })).toMatchObject({ name: "Diya", class: "5", roll_number: "12", guardian: "Kiran" });
    expect(staffValues({ name: "Ravi", designation: "Clerk", employee_code: "STF1", department: "Office" })).toMatchObject({ name: "Ravi", employee_id: "STF1", department: "Office" });
  });

  it("shows only safe QR images", () => {
    expect(safeImage("data:image/png;base64,AAAA")).toBe("data:image/png;base64,AAAA");
    expect(safeImage("javascript:alert(1)")).toBeNull();
    expect(safeImage("data:text/html;base64,AAAA")).toBeNull();
  });

  it("exports CSV safely", () => {
    expect(toCsv([{ name: 'A, "B"', value: "=SUM(1)" }], [{ label: "Name", value: (row) => row.name }, { label: "Value", value: (row) => row.value }])).toBe('Name,Value\r\n"A, ""B""",\'=SUM(1)');
  });
});
