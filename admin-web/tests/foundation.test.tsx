import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Button, ButtonTabs, EmptyState } from "@/components/ui";
import { invalidateApiCache } from "@/lib/api";
import { addSchoolAdmin, deleteSchool, saveSchool, setSchoolStatus } from "@/lib/school";

afterEach(cleanup);

let calls: { url: string; method: string; body: unknown }[] = [];

beforeEach(() => {
  calls = [];
  invalidateApiCache();
  window.localStorage.setItem("v1_access_token", "test-token");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      calls.push({ url: String(url).replace(/^.*\/api\/v1/, ""), method: init.method ?? "GET", body: typeof init.body === "string" ? JSON.parse(init.body) : undefined });
      return new Response(JSON.stringify({ id: 7 }), { status: 200, headers: { "Content-Type": "application/json" } });
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("school service", () => {
  it("sends each school action to Nitish's routes", async () => {
    await saveSchool({ name: "Green Valley" });
    await saveSchool({ name: "Green Valley" }, 7);
    await setSchoolStatus(7, "suspend");
    await deleteSchool(7);
    await addSchoolAdmin(7, { email: "a@school.test", password: "x", first_name: "A", last_name: "B", mobile: "1" });
    expect(calls.map((call) => `${call.method} ${call.url}`)).toEqual([
      "POST /super-admin/schools",
      "PATCH /super-admin/schools/7",
      "POST /super-admin/schools/7/suspend",
      "DELETE /super-admin/schools/7",
      "POST /super-admin/schools/7/admins",
    ]);
    expect(calls[0].body).toEqual({ name: "Green Valley" });
    expect(calls[4].body).toMatchObject({ email: "a@school.test", first_name: "A" });
  });
});

describe("shared UI", () => {
  it("maps button variants to the theme's classes and blocks clicks while busy", () => {
    const click = vi.fn();
    render(
      <>
        <Button onClick={click}>Save</Button>
        <Button variant="danger" busy busyLabel="Deleting…" onClick={click}>Delete</Button>
      </>,
    );
    expect(screen.getByRole("button", { name: "Save" }).className).toBe("btn-pill btn-pill-green");
    const busy = screen.getByRole("button", { name: "Deleting…" });
    expect(busy.className).toBe("btn-pill btn-pill-danger");
    fireEvent.click(busy);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(click).toHaveBeenCalledTimes(1);
  });

  it("switches button tabs and shows an empty state with an action", () => {
    const change = vi.fn();
    render(
      <>
        <ButtonTabs label="Report" value="a" onChange={change} tabs={[{ value: "a", label: "Students" }, { value: "b", label: "Staff" }]} />
        <EmptyState action={<button type="button">Add school</button>}>No schools yet.</EmptyState>
      </>,
    );
    expect(screen.getByRole("tab", { name: "Students" }).getAttribute("aria-selected")).toBe("true");
    fireEvent.click(screen.getByRole("tab", { name: "Staff" }));
    expect(change).toHaveBeenCalledWith("b");
    expect(screen.getByText("No schools yet.")).toBeTruthy();
  });
});
