import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SiteFooter from "@/components/marketing/SiteFooter";
import { StatusChip } from "@/components/ui/Badge";
import { StudentForm } from "@/components/people/StudentForm";
import { displayRootDomain, schoolAddress } from "@/lib/domains/core";
import { resetMockAcademics } from "@/lib/academics";

vi.mock("next/navigation", () => ({
  usePathname: () => "/school/students/new",
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

afterEach(cleanup);
afterEach(() => {
  vi.unstubAllEnvs();
});

beforeEach(() => {
  // jsdom has no scrollIntoView; the form scrolls to the first error.
  Element.prototype.scrollIntoView = vi.fn();
  window.localStorage.clear();
  resetMockAcademics();
});

describe("BUG-01: school address preview", () => {
  it("never shows localhost in a production build without a platform domain", () => {
    vi.stubEnv("NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN", "");
    vi.stubEnv("NODE_ENV", "production");
    expect(displayRootDomain()).toBe("");
    expect(schoolAddress("greenvalley")).toBe("greenvalley");
  });

  it("uses the configured platform domain, and localhost only in development", () => {
    vi.stubEnv("NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN", ".SchoolSarthi.app.");
    expect(schoolAddress("greenvalley")).toBe("greenvalley.schoolsarthi.app");
    vi.stubEnv("NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN", "");
    vi.stubEnv("NODE_ENV", "development");
    expect(schoolAddress("greenvalley")).toBe("greenvalley.localhost");
  });
});

describe("BUG-02: legal links", () => {
  it("links the footer to the Terms and Privacy pages, not Contact", () => {
    render(<SiteFooter />);
    expect(screen.getByRole("link", { name: "Privacy Policy" }).getAttribute("href")).toBe("/privacy");
    expect(screen.getByRole("link", { name: "Terms & Conditions" }).getAttribute("href")).toBe("/terms");
  });
});

describe("BUG-03: student admission placement errors", () => {
  it("clears the class and section errors once valid values are picked", async () => {
    render(<StudentForm student={null} cancelHref="/school/students" onSave={async () => undefined} />);
    fireEvent.click(await screen.findByRole("button", { name: "Admit student" }));
    expect(await screen.findByText("Choose a class.")).toBeTruthy();
    expect(screen.getByText("Choose a class first.")).toBeTruthy();

    const classSelect = screen.getByLabelText(/^Class/) as HTMLSelectElement;
    await waitFor(() => expect(classSelect.options.length).toBeGreaterThan(1));
    fireEvent.change(classSelect, { target: { value: classSelect.options[1].value } });
    await waitFor(() => expect(screen.queryByText("Choose a class.")).toBeNull());
    expect(screen.queryByText("Choose a class first.")).toBeNull();

    const sectionSelect = screen.getByLabelText(/^Section/) as HTMLSelectElement;
    await waitFor(() => expect(sectionSelect.options.length).toBeGreaterThan(1));
    fireEvent.click(screen.getByRole("button", { name: "Admit student" }));
    expect(await screen.findByText("Choose a section.")).toBeTruthy();
    fireEvent.change(sectionSelect, { target: { value: sectionSelect.options[1].value } });
    await waitFor(() => expect(screen.queryByText("Choose a section.")).toBeNull());
  });
});

describe("unknown statuses from the server", () => {
  it("shows an unknown status as a grey chip instead of breaking the page", () => {
    const MAP = { draft: { label: "Draft", tone: "grey" as const }, published: { label: "Published", tone: "green" as const } };
    render(
      <>
        <StatusChip map={MAP} value="published" />
        <StatusChip map={MAP} value={"archived" as keyof typeof MAP} />
        <StatusChip map={MAP} value={null} />
      </>,
    );
    expect(screen.getByText("Published").className).toContain("paid");
    expect(screen.getByText("archived").className).toContain("refunded");
    expect(screen.getByText("—")).toBeTruthy();
  });
});
