import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Hero from "@/components/marketing/Hero";
import { RequestDemoForm } from "@/components/marketing/RequestDemoForm";
import SiteFooter from "@/components/marketing/SiteFooter";
import { invalidateApiCache } from "@/lib/api";
import { feeAssignmentCopy } from "@/lib/ops/feeCopy";
import { addInstallment, splitInstallmentPlan } from "@/lib/ops/fees-math";
import { demoRequestProblems, EMPTY_DEMO_REQUEST } from "@/lib/marketing/demo";
import { REFUND_POLICY } from "@/lib/marketing/refund";

afterEach(cleanup);
afterEach(() => {
  vi.unstubAllGlobals();
});
beforeEach(() => {
  invalidateApiCache();
  window.localStorage.clear();
});

describe("Issue 1: fee assignment wording", () => {
  it("tells one story on the server: fees apply only once assigned", () => {
    const copy = feeAssignmentCopy(true);
    const all = Object.values(copy).join(" ");
    expect(all).not.toMatch(/automatically|already apply|outside the student's class/i);
    expect(copy.page).toMatch(/only after it's assigned/);
    expect(copy.empty).toMatch(/owe nothing until a fee structure is assigned/);
    expect(copy.dialogTitle).toBe("Assign a fee structure to a student");
    expect(copy.dialogDescription).toMatch(/standard fees and for optional fees/);
  });
});

describe("Issue 2: Request demo", () => {
  it("points the homepage button at the demo form, not login", () => {
    render(<Hero />);
    expect(screen.getByRole("link", { name: "Request demo" }).getAttribute("href")).toBe("/request-demo");
  });

  it("checks the required fields", () => {
    expect(Object.keys(demoRequestProblems(EMPTY_DEMO_REQUEST)).sort()).toEqual(["email", "name", "phone", "school_name"]);
    expect(demoRequestProblems({ ...EMPTY_DEMO_REQUEST, name: "Asha", school_name: "Green Valley", email: "asha@school.test", phone: "+91 98765 43210" })).toEqual({});
  });

  it("says the request wasn't sent when the server has no demo route, and never fakes success", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Not Found" }), { status: 404, headers: { "Content-Type": "application/json" } })));
    render(<RequestDemoForm />);
    fireEvent.change(screen.getByLabelText(/Your name/), { target: { value: "Asha Rao" } });
    fireEvent.change(screen.getByLabelText(/School name/), { target: { value: "Green Valley" } });
    fireEvent.change(screen.getByLabelText(/Email/), { target: { value: "asha@school.test" } });
    fireEvent.change(screen.getByLabelText(/Phone/), { target: { value: "9876543210" } });
    fireEvent.click(screen.getByRole("button", { name: "Request a demo" }));
    expect(await screen.findByText(/this request wasn't sent/)).toBeTruthy();
    expect(screen.queryByText(/has been sent/)).toBeNull();
  });

  it("confirms when the server accepts the request", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ id: 1 }), { status: 201, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    render(<RequestDemoForm />);
    fireEvent.change(screen.getByLabelText(/Your name/), { target: { value: "Asha Rao" } });
    fireEvent.change(screen.getByLabelText(/School name/), { target: { value: "Green Valley" } });
    fireEvent.change(screen.getByLabelText(/Email/), { target: { value: "asha@school.test" } });
    fireEvent.change(screen.getByLabelText(/Phone/), { target: { value: "9876543210" } });
    fireEvent.click(screen.getByRole("button", { name: "Request a demo" }));
    expect(await screen.findByText(/has been sent/)).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(String((fetchMock.mock.calls[0] as unknown[])[0])).toMatch(/\/public\/demo-requests$/);
  });
});

describe("Issue 3: Refund policy", () => {
  it("links the footer to the refund policy page and publishes no invented terms", () => {
    render(<SiteFooter />);
    expect(screen.getByRole("link", { name: "Refund Policy" }).getAttribute("href")).toBe("/refund-policy");
    expect(REFUND_POLICY.sections).toEqual([]);
  });
});

describe("Issue 4: installment labels", () => {
  const start = [{ name: "Full payment", due_date: "", amount: "" }];

  it("labels a ₹1,200 structure in two parts Installment 1 and 2, each ₹600", () => {
    const plan = splitInstallmentPlan(start, 1200, 2);
    expect(plan.map((row) => [row.name, row.amount])).toEqual([["Installment 1", "600.00"], ["Installment 2", "600.00"]]);
  });

  it("labels every preset and keeps totals", () => {
    expect(splitInstallmentPlan(splitInstallmentPlan(start, 1200, 3), 1200, 1).map((row) => row.name)).toEqual(["Full payment"]);
    for (const count of [1, 2, 3, 4, 12]) {
      const plan = splitInstallmentPlan(start, 1000, count);
      expect(plan.map((row) => row.name)).toEqual(count === 1 ? ["Full payment"] : Array.from({ length: count }, (_, i) => `Installment ${i + 1}`));
      expect(Math.round(plan.reduce((sum, row) => sum + Number(row.amount), 0) * 100)).toBe(100000);
    }
  });

  it("keeps names the admin typed", () => {
    const plan = splitInstallmentPlan([{ name: "Term 1", due_date: "2026-06-30", amount: "" }], 1200, 2);
    expect(plan.map((row) => row.name)).toEqual(["Term 1", "Installment 2"]);
    expect(plan[0].due_date).toBe("2026-06-30");
  });

  it("renames a lone Full payment when a second installment is added", () => {
    expect(addInstallment(start).map((row) => row.name)).toEqual(["Installment 1", "Installment 2"]);
  });
});
