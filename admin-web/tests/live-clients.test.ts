import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { invalidateApiCache } from "@/lib/api";
import { liveFees } from "@/lib/ops/fees";
import { liveTransport } from "@/lib/ops/transport";
import { liveGrading } from "@/lib/ops/grading";
import { httpPeopleService } from "@/lib/people/http";
import { liveOffline } from "@/lib/teaching/offline";

type Call = { url: string; method: string; headers: Headers; body: unknown };
let calls: Call[] = [];

function respond(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

beforeEach(() => {
  calls = [];
  invalidateApiCache();
  window.localStorage.setItem("v1_access_token", "test-token");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const headers = new Headers(init.headers);
      calls.push({ url: String(url), method: init.method ?? "GET", headers, body: typeof init.body === "string" ? JSON.parse(init.body) : init.body });
      return respond({ id: 9, items: [], total: 0, page: 1, page_size: 20, status: "pending", allocations: [] }, 201);
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Answers GETs by path (the first matching prefix wins) and records every call. */
function route(table: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const headers = new Headers(init.headers);
      const method = init.method ?? "GET";
      calls.push({ url: String(url), method, headers, body: typeof init.body === "string" ? JSON.parse(init.body) : init.body });
      const path = String(url).replace(/^.*\/api\/v1/, "").split("?")[0];
      if (method !== "GET") return respond({ id: 99, receipt_no: "RCPT-1", created_at: "2026-10-01T10:00:00", ...(typeof init.body === "string" ? JSON.parse(init.body) : {}) }, 201);
      const key = Object.keys(table).find((prefix) => path === prefix);
      const items = (key ? table[key] : []) as unknown[];
      return respond({ items, total: items.length, page: 1, page_size: 50 });
    }),
  );
}

describe("live fee client", () => {
  const fees = {
    "/school-admin/fee-assignments": [{ id: 11, structure_id: 5, student_id: 1 }, { id: 12, structure_id: 6, student_id: 1 }],
    "/school-admin/fee-structures": [
      { id: 5, name: "Annual", session_year_id: 1, class_id: 2, status: 1, amounts: [{ fee_type_id: 1, amount: 1000 }] },
      { id: 6, name: "Bus", session_year_id: 1, class_id: null, status: 1, amounts: [{ fee_type_id: 1, amount: 400 }] },
    ],
    "/school-admin/fee-types": [{ id: 1, name: "Tuition", category: "tuition", status: 1 }],
    "/school-admin/fee-concessions": [{ id: 3, student_id: 1, structure_id: 5, kind: "percent", value: 10, reason: "Sibling" }],
    "/school-admin/fee-payments": [{ id: 7, assignment_id: 11, student_id: 1, amount: 100, method: "cash", status: "success", paid_on: "2026-09-01", created_at: "2026-09-01T09:00:00" }],
  };

  it("works out what a student owes per installment, after concessions and payments, earliest due first", async () => {
    route({ ...fees, "/school-admin/fee-structures/5/installments": [{ id: 51, name: "Term 1", due_date: "2026-04-10", amount: 600 }, { id: 52, name: "Term 2", due_date: "2999-10-10", amount: 400 }] });
    const dues = await liveFees.dues(1);
    // Structure 5: 10% concession spread 60/40, ₹100 paid fills Term 1 first. Structure 6 has no installments.
    expect(dues.lines.map((line) => [line.installment_id, line.amount, line.concession, line.paid, line.balance, line.overdue])).toEqual([
      [51, 600, 60, 100, 440, true],
      [52, 400, 40, 0, 360, false],
      [0, 400, 0, 0, 400, false],
    ]);
    expect(dues.balance).toBe(1200);
    expect(dues.overdue).toBe(440);
  });

  it("collects through /fees/collect, one request per structure, with a key in the body", async () => {
    route(fees);
    await liveFees.recordPayment({ student_id: 1, amount: 1000, method: "cash", reference: null, remarks: null, paid_on: "2026-10-01", idempotency_key: "key-123" });
    const posts = calls.filter((call) => call.method === "POST");
    expect(posts.map((call) => call.url.replace(/^.*\/api\/v1/, ""))).toEqual(["/school-admin/fees/collect", "/school-admin/fees/collect"]);
    expect(posts.map((call) => call.body)).toEqual([
      { assignment_id: 11, amount: 800, method: "cash", reference: null, remarks: null, paid_on: "2026-10-01", idempotency_key: "key-123:11" },
      { assignment_id: 12, amount: 200, method: "cash", reference: null, remarks: null, paid_on: "2026-10-01", idempotency_key: "key-123:12" },
    ]);
  });

  it("refuses online payments and payments above the balance without posting", async () => {
    route(fees);
    await expect(liveFees.recordPayment({ student_id: 1, amount: 50, method: "online", reference: null, remarks: null, paid_on: "2026-10-01", idempotency_key: "k" })).rejects.toMatchObject({ status: 422 });
    await expect(liveFees.recordPayment({ student_id: 1, amount: 5000, method: "cash", reference: null, remarks: null, paid_on: "2026-10-01", idempotency_key: "k" })).rejects.toMatchObject({ status: 422 });
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(0);
  });

  it("saves a structure's amounts, then its installments as a set", async () => {
    route(fees);
    await liveFees.saveStructure({ name: "Class 2", session_year_id: 1, class_id: 2, items: [{ fee_type_id: 1, amount: 900 }], installments: [{ name: "Term 1", due_date: "2026-04-10", amount: 500 }, { name: "Term 2", due_date: "2026-10-10", amount: 400 }], late_fee_per_day: 0, status: 1 });
    const post = calls.find((call) => call.method === "POST");
    expect(post?.url).toMatch(/\/school-admin\/fee-structures$/);
    expect(post?.body).toEqual({ name: "Class 2", session_year_id: 1, class_id: 2, amounts: [{ fee_type_id: 1, amount: 900 }], status: 1 });
    const put = calls.find((call) => call.method === "PUT");
    expect(put?.url).toMatch(/\/school-admin\/fee-structures\/99\/installments$/);
    expect(put?.body).toEqual({ installments: [{ name: "Term 1", due_date: "2026-04-10", amount: 500, sort_order: 0 }, { name: "Term 2", due_date: "2026-10-10", amount: 400, sort_order: 1 }] });
  });

  it("cancels a payment with a reason", async () => {
    route(fees);
    await expect(liveFees.cancelPayment(7, " ")).rejects.toMatchObject({ status: 422 });
    await liveFees.cancelPayment(7, "Cheque bounced");
    expect(calls.at(-1)).toMatchObject({ method: "POST", body: { reason: "Cheque bounced" } });
    expect(calls.at(-1)?.url).toMatch(/\/school-admin\/fee-payments\/7\/cancel$/);
  });
});

describe("live transport and grading clients", () => {
  const transport = {
    "/school-admin/vehicles": [{ id: 1, name: "Bus 1", registration_no: "KA01", capacity: 1, status: 1 }],
    "/school-admin/transport-routes": [{ id: 2, name: "North", vehicle_id: 1, status: 1, stops: [{ id: 3, route_id: 2, name: "Gate", stop_order: 1, pickup_time: "07:30:00" }] }],
    "/school-admin/student-transport-assignments": [] as unknown[],
  };

  it("posts a student's transport to the server's route with only the fields it keeps", async () => {
    route(transport);
    const saved = await liveTransport.saveAssignment({ student_id: 1, route_id: 2, stop_id: 3, direction: "both", start_date: "2026-06-01", status: 1 });
    const post = calls.find((call) => call.method === "POST");
    expect(post?.url).toMatch(/\/school-admin\/student-transport-assignments$/);
    expect(post?.body).toEqual({ student_id: 1, route_id: 2, stop_id: 3 });
    expect(saved).toMatchObject({ route_name: "North", stop_name: "Gate" });
  });

  it("refuses a student when the route's vehicle is full", async () => {
    route({ ...transport, "/school-admin/student-transport-assignments": [{ id: 5, student_id: 9, route_id: 2, stop_id: 3 }] });
    await expect(liveTransport.saveAssignment({ student_id: 1, route_id: 2, stop_id: 3, direction: "both", start_date: "2026-06-01", status: 1 })).rejects.toMatchObject({ status: 409 });
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(0);
  });

  it("maps routes, stops and seats from the server", async () => {
    route(transport);
    const [north] = await liveTransport.routes();
    expect(north).toMatchObject({ vehicle_label: "KA01 (1 seats)", capacity: 1, stops: [{ name: "Gate", pickup_time: "07:30" }] });
  });

  it("reads grade bands as ranges and sends them back as bands with letters", async () => {
    route({ "/school-admin/grading-scales": [{ id: 4, name: "CBSE", is_default: 1, status: 1, bands: [{ id: 1, letter: "A", min_percent: 90, max_percent: 100, is_pass: 1 }] }] });
    const [scale] = await liveGrading.scales();
    expect(scale).toMatchObject({ is_default: true, ranges: [{ grade: "A", min_percent: 90, is_pass: true }] });
    await liveGrading.saveScale({ name: "CBSE", description: null, is_default: true, status: 1, ranges: [{ grade: "a", min_percent: 0, max_percent: 100, grade_point: null, remark: null, is_pass: true }] }, 4);
    const patch = calls.find((call) => call.method === "PATCH");
    expect(patch?.url).toMatch(/\/school-admin\/grading-scales\/4$/);
    expect((patch?.body as { bands: unknown[] }).bands).toEqual([{ letter: "A", min_percent: 0, max_percent: 100, grade_point: null, remark: null, is_pass: true, sort_order: 0 }]);
  });

  it("generates report cards for one exam", async () => {
    route({});
    await liveGrading.generate(12);
    expect(calls[0]).toMatchObject({ method: "POST", body: { exam_id: 12, grading_scale_id: null } });
    expect(calls[0].url).toMatch(/\/school-admin\/report-cards$/);
  });

  it("edits and removes an offline exam paper", async () => {
    route({});
    await liveOffline.updateSchedule(8, { subject_id: 1, teacher_user_id: null, exam_date: "2026-11-01", start_time: "09:00", end_time: "10:00", max_marks: 80, passing_marks: 30 });
    await liveOffline.removeSchedule(8);
    expect(calls.map((call) => [call.method, call.url.replace(/^.*\/api\/v1/, "")])).toEqual([
      ["PATCH", "/school-admin/offline-exam-schedules/8"],
      ["DELETE", "/school-admin/offline-exam-schedules/8"],
    ]);
  });
});

describe("live people client", () => {
  it("admits a student with a new guardian inline and no password", async () => {
    await httpPeopleService.createStudent({
      first_name: "Diya",
      last_name: "Patel",
      dob: "2012-06-10",
      gender: "female",
      admission_date: "2026-04-10",
      session_year_id: 2,
      class_section_id: 8,
      roll_number: 2,
      email: "",
      mobile: "",
      current_address: "4 Park Street",
      permanent_address: null,
      status: 1,
      guardian: { first_name: "Kiran", last_name: "Patel", email: "kiran@example.test", mobile: "9123456789", relationship: "Mother", password: "ignored" },
    });
    const call = calls[0];
    expect(call.url).toMatch(/\/school-admin\/students$/);
    expect(call.body).toMatchObject({ dob: "2012-06-10", gender: "female", current_address: "4 Park Street", email: null, admission_no: null, guardian: { relationship: "Mother", email: "kiran@example.test" } });
    expect((call.body as { guardian: Record<string, unknown> }).guardian).not.toHaveProperty("password");
  });

  it("puts the server's duplicate roll number sentence under the roll number field", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => respond({ detail: "Roll number is already used in this class section and session" }, 409)));
    await expect(
      httpPeopleService.updateStudent(1, { first_name: "A", last_name: "B", dob: "2012-01-01", gender: "male", admission_no: "ADM1", admission_date: "2026-04-01", session_year_id: 2, class_section_id: 8, roll_number: 1, current_address: "x", status: 1 }),
    ).rejects.toMatchObject({ status: 409, fieldErrors: { roll_number: expect.stringMatching(/Roll number/) } });
  });
});

describe("timetable classroom", () => {
  it("saves the classroom in the server's room field and still reads rooms kept in older notes", async () => {
    const { noteWithRoom, roomFromNote, liveTimetable } = await import("@/lib/teaching/timetable");
    expect(noteWithRoom("12", "Bring lab coats")).toBe("Room: 12\nBring lab coats");
    expect(noteWithRoom(" ", "Only a note")).toBe("Only a note");
    expect(noteWithRoom(null, null)).toBeNull();
    expect(roomFromNote("Room: Lab 2\nBring lab coats")).toEqual({ room: "Lab 2", note: "Bring lab coats" });
    expect(roomFromNote("Room: 12")).toEqual({ room: "12", note: null });
    expect(roomFromNote("Remember the Room: change")).toEqual({ room: null, note: "Remember the Room: change" });
    await liveTimetable.create({ session_year_id: 1, class_section_id: 2, subject_id: 3, teacher_user_id: 4, day: "monday", start_time: "08:30", end_time: "09:15", note: null, room: "12" });
    expect(calls[0].url).toMatch(/\/school-admin\/timetable-entries$/);
    expect(calls[0].body).toMatchObject({ room: "12", note: null });
    const { withRoom } = await import("@/lib/teaching/timetable");
    expect(withRoom("Lab 1", "Bring coats")).toEqual({ room: "Lab 1", note: "Bring coats" });
    expect(withRoom(null, "Room: 12\nBring coats")).toEqual({ room: "12", note: "Bring coats" });
  });
});
