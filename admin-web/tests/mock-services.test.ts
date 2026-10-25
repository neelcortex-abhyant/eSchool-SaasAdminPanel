import { beforeEach, describe, expect, it } from "vitest";
import { mockFees } from "@/lib/ops/fees";
import { resetOpsMock } from "@/lib/ops/store";
import { mockTransport } from "@/lib/ops/transport";

beforeEach(() => {
  window.localStorage.clear();
  resetOpsMock();
});

describe("sample fee client", () => {
  it("records an office payment once per idempotency key and issues a receipt", async () => {
    const before = await mockFees.dues(1);
    const input = { student_id: 1, amount: 1000, method: "cash" as const, reference: null, remarks: null, paid_on: "2026-10-01", idempotency_key: "same-key" };
    const first = await mockFees.recordPayment(input);
    const again = await mockFees.recordPayment(input);
    expect(first.status).toBe("success");
    expect(first.receipt_no).toMatch(/^RCPT-2026-\d{4}$/);
    expect(again.id).toBe(first.id);
    const after = await mockFees.dues(1);
    expect(after.balance).toBeCloseTo(before.balance - 1000, 2);
  });

  it("keeps online payments pending: not counted as paid and no receipt", async () => {
    const before = await mockFees.dues(1);
    const payment = await mockFees.recordPayment({ student_id: 1, amount: 500, method: "online", reference: "LINK-1", remarks: null, paid_on: "2026-10-01", idempotency_key: "online-1" });
    expect(payment.status).toBe("pending");
    expect(payment.receipt_no).toBeNull();
    const after = await mockFees.dues(1);
    expect(after.paid).toBe(before.paid);
    expect(after.pending).toBe(before.pending + 500);
    await expect(mockFees.receipt(payment.id)).rejects.toMatchObject({ status: 409 });
  });

  it("refuses a payment above the balance", async () => {
    const dues = await mockFees.dues(1);
    await expect(mockFees.recordPayment({ student_id: 1, amount: dues.balance + 1, method: "cash", reference: null, remarks: null, paid_on: "2026-10-01", idempotency_key: "too-much" })).rejects.toMatchObject({
      status: 422,
      fieldErrors: { amount: expect.stringMatching(/owes/) },
    });
  });

  it("applies a full exemption", async () => {
    const dues = await mockFees.dues(8);
    expect(dues.concession).toBe(dues.total);
    expect(dues.balance).toBe(0);
  });
});

describe("sample transport client", () => {
  it("refuses a student when the route's vehicle is full", async () => {
    // Route 2 uses a 3-seat van that already carries 3 students.
    await expect(mockTransport.saveAssignment({ student_id: 2, route_id: 2, stop_id: 4, direction: "both", start_date: "2026-07-01", status: 1 })).rejects.toMatchObject({
      status: 409,
      fieldErrors: { route_id: expect.stringMatching(/3 seats and 3 are taken/) },
    });
  });

  it("refuses a stop from another route and a second active assignment", async () => {
    await expect(mockTransport.saveAssignment({ student_id: 2, route_id: 1, stop_id: 4, direction: "both", start_date: "2026-07-01", status: 1 })).rejects.toMatchObject({ status: 422 });
    await expect(mockTransport.saveAssignment({ student_id: 1, route_id: 1, stop_id: 2, direction: "both", start_date: "2026-07-01", status: 1 })).rejects.toMatchObject({ status: 409 });
  });

  it("assigns a student while seats remain", async () => {
    const saved = await mockTransport.saveAssignment({ student_id: 2, route_id: 1, stop_id: 2, direction: "pickup", start_date: "2026-07-01", status: 1 });
    expect(saved).toMatchObject({ route_name: "Route 1 – Indiranagar", stop_name: "Domlur Flyover", direction: "pickup" });
  });
});
