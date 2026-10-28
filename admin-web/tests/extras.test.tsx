import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { invalidateApiCache } from "@/lib/api";
import { RecordForm, ResourcePage } from "@/components/extras/ResourcePage";
import { summarise } from "@/components/extras/StaffAttendance";
import { fillTemplate, payrollTotals } from "@/components/extras/Tools";
import { csvRows, importErrors, parseCsv, STUDENT_IMPORT_COLUMNS } from "@/lib/extras/csv";
import { initialValues, problems, toBody } from "@/lib/extras/form";
import { EXTRA_PAGES } from "@/lib/extras/pages";
import { EXTRA_SLUGS } from "@/components/extras/registry";
import { SCHOOL_ADMIN_NAV } from "@/lib/nav";
import type { ResourceConfig } from "@/lib/extras/types";

afterEach(cleanup);

type Call = { url: string; method: string; body: unknown };
let calls: Call[] = [];

function respond(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** GET answers by path; other methods echo the body back with an id. */
function serve(table: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const method = init.method ?? "GET";
      const body = typeof init.body === "string" ? JSON.parse(init.body) : undefined;
      calls.push({ url: String(url), method, body });
      const path = String(url).replace(/^.*\/api\/v1/, "").split("?")[0];
      if (method !== "GET") return respond({ id: 50, ...(body ?? {}) }, method === "POST" ? 201 : 200);
      if (path in table) {
        const value = table[path];
        return respond(Array.isArray(value) ? { items: value, total: value.length, page: 1, page_size: 50 } : value);
      }
      return respond({ items: [], total: 0, page: 1, page_size: 50 });
    }),
  );
}

beforeEach(() => {
  calls = [];
  invalidateApiCache();
  window.localStorage.setItem("v1_access_token", "test-token");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const holidays = EXTRA_PAGES["holiday-list"] as ResourceConfig;
const income = EXTRA_PAGES["manage-income"] as ResourceConfig;

describe("record forms", () => {
  it("checks required fields the way the server does", () => {
    expect(problems(holidays.fields, initialValues(holidays.fields), false)).toEqual({ title: "Enter title.", holiday_date: "Enter date." });
  });

  it("sends typed values, nulls for empty fields, and leaves create-only fields out of edits", () => {
    const values = { ...initialValues(income.fields), title: " Hall rent ", amount: "1500", income_date: "", category_id: "3", session_year_id: "2" };
    expect(toBody(income.fields, values, false)).toEqual({ title: "Hall rent", amount: 1500, income_date: null, category_id: 3, session_year_id: 2 });
    expect(toBody(income.fields, values, true)).toEqual({ title: "Hall rent", amount: 1500, income_date: null });
  });

  it("reads server values into the form (dates, times, 0/1 flags)", () => {
    const sliders = EXTRA_PAGES.sliders as ResourceConfig;
    expect(initialValues(sliders.fields, { title: "Welcome", status: 1, sort_order: 2 })).toMatchObject({ title: "Welcome", status: "1", sort_order: "2" });
    const shifts = EXTRA_PAGES.shift as ResourceConfig;
    expect(initialValues(shifts.fields, { name: "Morning", start_time: "07:30:00" }).start_time).toBe("07:30");
  });

  it("adds seconds to a date and time before sending it", () => {
    const online = EXTRA_PAGES["online-classes"] as ResourceConfig;
    expect(toBody(online.fields, { ...initialValues(online.fields), title: "Maths", scheduled_at: "2026-11-02T09:30" }, true)).toMatchObject({ scheduled_at: "2026-11-02T09:30:00" });
  });
});

describe("page configuration", () => {
  it("has a menu entry for every page and a page for every slug it claims", () => {
    const hrefs = JSON.stringify(SCHOOL_ADMIN_NAV);
    for (const slug of EXTRA_SLUGS) expect(hrefs, slug).toContain(`/school/${slug}"`);
  });

  it("only offers edit where the fields make sense", () => {
    for (const [slug, config] of Object.entries(EXTRA_PAGES)) {
      if (config.kind !== "resource") continue;
      expect(config.path.startsWith("/"), slug).toBe(true);
      expect(new Set(config.fields.map((field) => field.key)).size, slug).toBe(config.fields.length);
      if (config.canCreate !== false) expect(config.fields.length, slug).toBeGreaterThan(0);
    }
  });
});

describe("resource page", () => {
  it("lists the server's rows and adds a record with the server's field names", async () => {
    serve({ "/school-admin/me": { id: 1 }, "/school-admin/holidays": [{ id: 1, title: "Diwali", holiday_date: "2026-11-08", end_date: null, description: null }] });
    render(<ResourcePage config={holidays} icon={null} />);
    expect(await screen.findByText("Diwali")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Add holiday" }));
    fireEvent.change(screen.getByLabelText(/^Title/), { target: { value: "Christmas" } });
    fireEvent.change(screen.getByLabelText(/^Date/), { target: { value: "2026-12-25" } });
    // The header button and the form's submit button share the label; the form's comes last.
    fireEvent.click(screen.getAllByRole("button", { name: "Add holiday" }).at(-1) as HTMLElement);
    await waitFor(() => expect(calls.some((call) => call.method === "POST")).toBe(true));
    const post = calls.find((call) => call.method === "POST");
    expect(post?.url).toMatch(/\/school-admin\/holidays$/);
    expect(post?.body).toEqual({ title: "Christmas", holiday_date: "2026-12-25", end_date: null, description: null });
  });

  it("patches an edit at the record's path without create-only fields", async () => {
    serve({});
    const onSaved = vi.fn();
    render(<RecordForm config={income} row={{ id: 7, title: "Rent", amount: 100, income_date: "2026-10-01", category_id: 2, session_year_id: 1 }} onClose={() => undefined} onSaved={onSaved} />);
    fireEvent.change(screen.getByLabelText(/^Amount/), { target: { value: "250" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(false));
    expect(calls[calls.length - 1]).toMatchObject({ method: "PATCH", body: { title: "Rent", amount: 250, income_date: "2026-10-01" } });
    expect(calls[calls.length - 1].url).toMatch(/\/school-admin\/incomes\/7$/);
  });
});

describe("helpers", () => {
  it("parses quoted CSV values", () => {
    expect(parseCsv('a,b\n"x, y","say ""hi"""\r\n\n1,2')).toEqual([["a", "b"], ["x, y", 'say "hi"'], ["1", "2"]]);
  });

  it("checks import rows before sending them", () => {
    const header = STUDENT_IMPORT_COLUMNS.map((column) => column.key).join(",");
    const ok = csvRows(`${header}\nDiya,Patel,diya@example.com,A1,2026-04-01,2,8,15,,`, STUDENT_IMPORT_COLUMNS);
    expect(ok.problems).toEqual([]);
    expect(ok.rows[0]).toEqual({ first_name: "Diya", last_name: "Patel", email: "diya@example.com", admission_no: "A1", admission_date: "2026-04-01", session_year_id: 2, class_section_id: 8, guardian_id: 15 });
    expect(csvRows("first_name\nA", STUDENT_IMPORT_COLUMNS).problems[0]).toMatch(/Missing columns/);
    expect(csvRows(`${header}\nDiya,,d@x.io,A1,2026-04-01,two,8,15,,`, STUDENT_IMPORT_COLUMNS).problems).toEqual(["Row 2: last_name is empty.", "Row 2: session_year_id must be a number."]);
  });

  it("reads the server's per-row import errors", () => {
    expect(importErrors('{"errors": [{"row": 0, "detail": "email is required"}]}')).toEqual(["Row 2: email is required"]);
    expect(importErrors("Something else")).toEqual([]);
  });

  it("counts staff attendance per person", () => {
    const people = [{ staff_id: 1, user_id: 10, name: "Asha", designation: "Clerk", kind: "staff" as const }];
    expect(summarise([{ staff_id: 1, status: "present" }, { staff_id: 1, status: "late" }, { staff_id: 1, status: "absent" }, { staff_id: 2, status: "leave" }], people)).toEqual([
      { id: 1, name: "Asha", designation: "Clerk", present: 1, absent: 1, late: 1, leave: 0, total: 3 },
      { id: 2, name: "Staff #2", designation: "", present: 0, absent: 0, late: 0, leave: 1, total: 1 },
    ]);
  });

  it("works out net pay and fills certificate text", () => {
    expect(payrollTotals([{ gross: "30000", deductions: "1500.5" }, { gross: "", deductions: "" }])).toEqual({ nets: [28499.5, 0], total: 28499.5 });
    expect(fillTemplate("This is to certify that {student_name} ({ admission_no }) {unknown}", { student_name: "Diya", admission_no: "A1" })).toBe("This is to certify that Diya (A1) {unknown}");
  });
});

describe("pickers instead of raw ids", () => {
  it("staff leave picks the person and defaults to the current session", async () => {
    const leave = EXTRA_PAGES["staff-leave"] as ResourceConfig;
    serve({
      "/school-admin/staff": [{ id: 31, staff_id: 5, name: "Asha Rao", designation: "Clerk" }],
      "/school-admin/teachers": [],
      "/school-admin/academics/sessions": [{ id: 1, name: "2025-26", is_active: 0 }, { id: 2, name: "2026-27", is_active: 1 }],
    });
    render(<RecordForm config={leave} row={null} onClose={() => undefined} onSaved={() => undefined} />);
    await screen.findByRole("option", { name: "Asha Rao · Clerk" });
    await waitFor(() => expect((screen.getByLabelText(/^Academic session/) as HTMLSelectElement).value).toBe("2"));
    fireEvent.change(screen.getByLabelText(/^Teacher or staff member/), { target: { value: "31" } });
    fireEvent.change(screen.getByLabelText(/^Reason/), { target: { value: "Fever" } });
    fireEvent.change(screen.getByLabelText(/^From/), { target: { value: "2026-10-28" } });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: "2026-10-29" } });
    fireEvent.click(screen.getByRole("button", { name: "Add leave" }));
    await waitFor(() => expect(calls.some((call) => call.method === "POST")).toBe(true));
    expect(calls.find((call) => call.method === "POST")).toMatchObject({ body: { user_id: 31, reason: "Fever", from_date: "2026-10-28", to_date: "2026-10-29", session_year_id: 2, status: "0" } });
  });

  it("no page asks for a raw id", () => {
    for (const [slug, config] of Object.entries(EXTRA_PAGES)) {
      if (config.kind === "report") continue;
      for (const field of config.fields) if (/_id$/.test(field.key) && !field.rawId) expect(field.type, `${slug}.${field.key}`).toBe("ref");
    }
  });
});

describe("ID cards", () => {
  it("keeps separate student and staff text in the server's one settings record", async () => {
    const { idCardBody, parseIdCardSettings } = await import("@/lib/extras/idCards");
    const body = idCardBody({ student: { front: " Green Valley School ", back: "Call 100" }, staff: { front: "STAFF", back: "Office: 080-1234" } });
    expect(body).toEqual({ front_template: "Green Valley School", back_template: "Call 100", show_fields: { student: { front: "Green Valley School", back: "Call 100" }, staff: { front: "STAFF", back: "Office: 080-1234" } } });
    // The server returns show_fields as a JSON string.
    expect(parseIdCardSettings({ show_fields_json: JSON.stringify(body.show_fields) }).staff).toEqual({ front: "STAFF", back: "Office: 080-1234" });
    // Settings saved before the split apply to both cards.
    expect(parseIdCardSettings({ front_template: "Old", back_template: null, show_fields_json: null })).toEqual({ student: { front: "Old", back: "" }, staff: { front: "Old", back: "" } });
  });

  it("uses the card's own text and fills its placeholders", async () => {
    const { cardOf } = await import("@/components/extras/Tools");
    const settings = { show_fields_json: JSON.stringify({ student: { front: "Student of {class}", back: "" }, staff: { front: "{designation} · {employee_id}", back: "" } }) };
    const student = cardOf("student", { first_name: "Diya", last_name: "Patel", settings }, [["Class", "5 A"]], { class: "5 A" });
    const staff = cardOf("staff", { first_name: "Ravi", last_name: "K", settings }, [["Designation", "Clerk"]], { designation: "Clerk", employee_id: "STF001" });
    expect([student.title, student.front, student.kind]).toEqual(["Diya Patel", "Student of 5 A", "student"]);
    expect([staff.front, staff.kind]).toEqual(["Clerk · STF001", "staff"]);
  });
});

describe("teachers: bulk upload and salary", () => {
  it("checks teacher rows before adding any", async () => {
    const { TEACHER_IMPORT_COLUMNS, teacherRowProblems } = await import("@/lib/extras/csv");
    const header = TEACHER_IMPORT_COLUMNS.map((column) => column.key).join(",");
    const parsed = csvRows(`${header}\nNeha,Sharma,neha@example.com,secret123,,female,,PGT,Science,2026-04-01,45000,\nRavi,K,neha@example.com,short,,,,,,04/01/2026,-5,`, TEACHER_IMPORT_COLUMNS);
    expect(parsed.rows[0]).toMatchObject({ first_name: "Neha", email: "neha@example.com", password: "secret123", salary: 45000 });
    expect(teacherRowProblems(parsed.rows)).toEqual([
      "Row 3: neha@example.com appears twice in the file.",
      "Row 3: password must be at least 8 characters.",
      "Row 3: salary can't be negative.",
      "Row 3: joining_date must be YYYY-MM-DD.",
    ]);
  });

  it("saves a salary on the teacher or staff route", async () => {
    const { salaryPath } = await import("@/components/extras/Tools");
    expect(salaryPath({ kind: "teacher", user_id: 12 })).toBe("/teachers/12");
    expect(salaryPath({ kind: "staff", user_id: 30 })).toBe("/staff/30");
  });
});

describe("settings pages (backend 0040)", () => {
  it("reads and writes nested settings and never sends an empty secret", () => {
    const payment = EXTRA_PAGES["payment-settings"] as import("@/lib/extras/types").SettingsConfig;
    const values = initialValues(payment.fields, { provider: "fee_payment_gateway", configured: true, public_config: { enabled: 1, provider: "razorpay", mode: "live", key_id: "rzp_live_x", currency: "INR" } });
    expect(values).toMatchObject({ "public_config.enabled": "1", "public_config.mode": "live", "public_config.key_id": "rzp_live_x", secret: "" });
    expect(toBody(payment.fields, values, false)).toEqual({ public_config: { enabled: 1, provider: "razorpay", mode: "live", key_id: "rzp_live_x", currency: "INR" }, clear_secret: 0 });
    expect(toBody(payment.fields, { ...values, secret: " new-secret " }, false)).toMatchObject({ secret: "new-secret" });
  });

  it("saves leave policy as an object and list fields as arrays", () => {
    const leave = EXTRA_PAGES["leave-settings"] as import("@/lib/extras/types").SettingsConfig;
    const body = toBody(leave.fields, { ...initialValues(leave.fields), "policy.staff_casual_days": "12", "policy.allow_half_day": "1", notes: "" }, false);
    expect(body).toEqual({ policy: { staff_casual_days: 12, staff_sick_days: null, student_max_days_per_month: null, approval: "admin", allow_half_day: 1 }, notes: null });
    const fields = (EXTRA_PAGES["additional-user-fields"] as ResourceConfig).fields;
    expect(toBody(fields, { ...initialValues(fields), label: "Blood group", field_key: "blood_group", field_type: "select", options: "A+, B+ , O+" }, false)).toMatchObject({ options: ["A+", "B+", "O+"], entity_type: "student", required: 0 });
    expect(initialValues(fields, { options: ["A+", "B+"] }).options).toBe("A+, B+");
  });

  it("reads third-party settings written one per line", async () => {
    const { configLines, parseConfigLines } = await import("@/components/extras/Support");
    expect(parseConfigLines("sender_id=SCHOOL\n\nregion = in\nbroken line")).toEqual({ sender_id: "SCHOOL", region: "in" });
    expect(configLines({ sender_id: "SCHOOL", region: "in" })).toBe("sender_id=SCHOOL\nregion=in");
  });
});
