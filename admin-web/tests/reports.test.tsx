import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { invalidateApiCache } from "@/lib/api";
import { defaultRange, ReportsDashboard } from "@/components/reports/ReportsDashboard";
import { loadReport, monthsBetween, reportCsv, type Report } from "@/lib/reports/analytics";

const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  usePathname: () => "/school/reports",
  useRouter: () => ({ replace, push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(search),
}));

afterEach(cleanup);

let urls: string[] = [];

function respond(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** GETs answered by exact path; a number answers with that error status. */
function serve(table: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      urls.push(String(url));
      const path = String(url).replace(/^.*\/api\/v1/, "").split("?")[0];
      const value = table[path];
      if (typeof value === "number") return respond({ detail: `Server error ${value}` }, value);
      if (value === undefined) return respond({ items: [], total: 0, page: 1, page_size: 50 });
      return respond(Array.isArray(value) ? { items: value, total: value.length, page: 1, page_size: 50 } : value);
    }),
  );
}

const STAFF_SERVER = {
  "/auth/me": { id: 1, role: "school_admin", school_id: 3 },
  "/school-admin/staff": [{ id: 31, staff_id: 5, name: "Asha Rao", designation: "Clerk", department: "Office" }],
  "/school-admin/teachers": [{ id: 32, staff_id: 6, name: "Ravi Iyer", designation: "Teacher" }],
  "/school-admin/reports/staff": { total: 2, by_employment_status: { active: 2 } },
  "/school-admin/staff-attendance/reports": {
    items: [
      { id: 1, staff_id: 5, attendance_date: "2026-10-01", status: "present" },
      { id: 2, staff_id: 6, attendance_date: "2026-10-01", status: "absent" },
      { id: 3, staff_id: 5, attendance_date: "2026-10-02", status: "late" },
      { id: 4, staff_id: 6, attendance_date: "2026-10-02", status: "present" },
    ],
    total: 4,
    summary: {},
  },
  "/school-admin/leave-types": [{ id: 2, code: "SL", name: "Sick leave", days_per_year: 10, applies_to: "staff", is_active: true }],
  "/school-admin/academics/leaves": [
    { id: 41, user_id: 31, student_id: null, reason: "Fever", leave_type: "Sick leave", from_date: "2026-10-05", to_date: "2026-10-06", status: 1 },
    { id: 42, user_id: 32, student_id: null, reason: "Trip", leave_type: "Sick leave", from_date: "2026-10-20", to_date: "2026-10-20", status: 0 },
    { id: 43, user_id: 32, student_id: null, reason: "Old", leave_type: "Sick leave", from_date: "2025-01-01", to_date: "2025-01-02", status: 1 },
  ],
  "/school-admin/payroll/summary": { items: [{ month: "2026-09", processed: 2, pending: 0, failed: 0, total_net: 61000 }] },
};

const FILTER = { sessionId: "" as const, classId: "" as const, sectionId: "" as const, from: "2026-10-01", to: "2026-10-31" };

beforeEach(() => {
  urls = [];
  search = "";
  replace.mockReset();
  invalidateApiCache();
  window.localStorage.clear();
  window.localStorage.setItem("v1_access_token", "test-token");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("report helpers", () => {
  it("lists every month in the range, across a year end", () => {
    expect(monthsBetween("2026-11-15", "2027-02-01")).toEqual(["2026-11", "2026-12", "2027-01", "2027-02"]);
    expect(monthsBetween("2026-05-01", "2026-04-01")).toEqual([]);
  });

  it("defaults to the last six months", () => {
    expect(defaultRange(new Date(2026, 9, 30))).toEqual({ from: "2026-05-01", to: "2026-10-30" });
  });

  it("exports every table under its title and neutralises spreadsheet formulas", () => {
    const report: Report = {
      cards: [{ label: "Students", value: "12" }],
      charts: [],
      tables: [{ title: "By class", columns: ["Class", "Total"], rows: [["=SUM(A1)", 3], ["Grade, 2", 4]], empty: "" }],
      notes: [],
      warnings: [],
    };
    const csv = reportCsv(report, "Students report");
    expect(csv).toContain("Students report\r\nStudents,12,");
    expect(csv).toContain("By class\r\nClass,Total\r\n'=SUM(A1),3\r\n\"Grade, 2\",4");
  });
});

describe("staff report", () => {
  it("combines the server's staff, attendance, leave and payroll routes", async () => {
    serve(STAFF_SERVER);
    const report = await loadReport("staff", FILTER);
    const card = (label: string) => report.cards.find((item) => item.label === label);
    expect(card("Staff")).toMatchObject({ value: "2", note: "1 teachers" });
    // Present and late count as attended: 3 of 4.
    expect(card("Attendance")?.value).toBe("75%");
    // The 2025 leave is outside the dates; one approved request of two days, one pending.
    expect(card("Leave requests")).toMatchObject({ value: "2", note: "2 approved days" });
    expect(card("Pending leave")?.value).toBe("1");
    expect(card("Payroll 2026")?.value).toBe("₹61,000");
    expect(report.tables.find((table) => table.title === "Leave by type")?.rows).toEqual([["Sick leave", 2, 3, 1, 1, 0]]);
    expect(urls.some((url) => url.includes("/staff-attendance/reports?from_date=2026-10-01&to_date=2026-10-31"))).toBe(true);
    expect(urls.some((url) => url.includes("/payroll/summary?year=2026"))).toBe(true);
    expect(report.warnings).toEqual([]);
  });

  it("still shows the other parts when one route fails", async () => {
    serve({ ...STAFF_SERVER, "/school-admin/payroll/summary": 500 });
    const report = await loadReport("staff", FILTER);
    expect(report.warnings).toEqual([expect.stringMatching(/^Payroll summary: /)]);
    expect(report.cards.find((item) => item.label === "Payroll 2026")?.value).toBe("—");
    expect(report.cards.find((item) => item.label === "Attendance")?.value).toBe("75%");
  });

  it("lists every part the server couldn't answer", async () => {
    serve(Object.fromEntries(Object.keys(STAFF_SERVER).map((path) => [path, 500])));
    const report = await loadReport("staff", FILTER);
    expect(report.warnings.map((warning) => warning.split(":")[0])).toEqual(["Employment summary", "Staff attendance", "Leave", "Payroll summary"]);
  });
});

describe("reports dashboard", () => {
  it("shows the chosen category and switches categories through the address", async () => {
    search = "category=staff";
    serve(STAFF_SERVER);
    render(<ReportsDashboard />);
    expect(await screen.findByText("Leave by type")).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Staff" }).getAttribute("aria-selected")).toBe("true");
    // Staff reports don't take class filters.
    expect(screen.queryByLabelText("Filter by class")).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: "Finance" }));
    expect(replace).toHaveBeenCalledWith("/school/reports?category=finance", { scroll: false });
  });

  it("explains a backwards date range instead of loading", async () => {
    search = "category=staff";
    serve(STAFF_SERVER);
    render(<ReportsDashboard />);
    await screen.findByText("Leave by type");
    const before = urls.length;
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-12-01" } });
    expect(await screen.findByText("The start date is after the end date.")).toBeTruthy();
    await waitFor(() => expect(urls.length).toBe(before));
  });
});
