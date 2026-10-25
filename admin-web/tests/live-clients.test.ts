import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { invalidateApiCache } from "@/lib/api";
import { liveFees } from "@/lib/ops/fees";
import { liveTransport } from "@/lib/ops/transport";
import { liveGrading } from "@/lib/ops/grading";
import { httpPeopleService } from "@/lib/people/http";

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

describe("live fee client", () => {
  it("sends payments with the idempotency key in a header, not the body", async () => {
    await liveFees.recordPayment({ student_id: 4, amount: 500, method: "online", reference: null, remarks: null, paid_on: "2026-10-01", idempotency_key: "key-123" });
    const call = calls[0];
    expect(call.url).toMatch(/\/api\/v1\/school-admin\/fee-payments$/);
    expect(call.method).toBe("POST");
    expect(call.headers.get("Idempotency-Key")).toBe("key-123");
    expect(call.headers.get("Authorization")).toBe("Bearer test-token");
    expect(call.body).toEqual({ student_id: 4, amount: 500, method: "online", reference: null, remarks: null, paid_on: "2026-10-01" });
  });

  it("filters payments with the contract's query names", async () => {
    await liveFees.payments({ page: 2, studentId: 4, status: "pending", from: "2026-01-01", to: "2026-02-01" });
    expect(calls[0].url).toContain("/school-admin/fee-payments?");
    expect(calls[0].url).toContain("student_id=4");
    expect(calls[0].url).toContain("status=pending");
    expect(calls[0].url).toContain("from_date=2026-01-01");
    expect(calls[0].url).toContain("to_date=2026-02-01");
  });

  it("checks a structure on the client before sending it", async () => {
    await expect(
      liveFees.saveStructure({ name: "X", session_year_id: 1, class_id: 1, items: [{ fee_type_id: 1, amount: 100 }], installments: [{ name: "A", due_date: "2026-01-01", amount: 50 }], late_fee_per_day: 0, status: 1 }),
    ).rejects.toMatchObject({ status: 422 });
    expect(calls).toHaveLength(0);
  });
});

describe("live transport and grading clients", () => {
  it("posts a transport assignment to the contract route", async () => {
    await liveTransport.saveAssignment({ student_id: 1, route_id: 2, stop_id: 3, direction: "both", start_date: "2026-06-01", status: 1 });
    expect(calls[0]).toMatchObject({ method: "POST", body: { student_id: 1, route_id: 2, stop_id: 3, direction: "both", start_date: "2026-06-01", status: 1 } });
    expect(calls[0].url).toMatch(/\/school-admin\/transport\/assignments$/);
  });

  it("asks for a report card for one session", async () => {
    await liveGrading.reportCard(7, 2, 3);
    expect(calls[0].url).toMatch(/\/school-admin\/report-cards\/7\?session_year_id=2&grading_scale_id=3$/);
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
