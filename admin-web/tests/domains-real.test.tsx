import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SiteBeingSetUp } from "@/components/domains/SchoolLanding";
import { checkAvailability, domainRequestFields } from "@/lib/domains/client";
import { siteFromSchool, slugOf } from "@/lib/domains/school";

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

describe("registration domain fields (backend's live fields)", () => {
  it("sends the subdomain prefix for a default domain and the full host for a custom one", () => {
    expect(domainRequestFields({ type: "default", slug: "green-valley" })).toEqual({ domain_type: "default", domain: "green-valley" });
    expect(domainRequestFields({ type: "custom", slug: "green-valley", custom_domain: "portal.gv.edu" })).toEqual({ domain_type: "custom", domain: "portal.gv.edu" });
  });

  it("only checks the format until the backend has an availability route", async () => {
    await expect(checkAvailability("green-valley")).resolves.toMatchObject({ available: true, unchecked: true });
    await expect(checkAvailability("www")).resolves.toMatchObject({ available: false });
  });
});

describe("the school's own record as its website", () => {
  it("uses the registered name, logo, address, phone and email", () => {
    vi.stubEnv("NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN", "eschool.example.com");
    const site = siteFromSchool({
      id: 12,
      name: "Green Valley Public School",
      tagline: "Grow with curiosity",
      logo: "https://cdn.example.com/gv.png",
      address: "4 Hill Road, Pune, Maharashtra, 411001, India",
      support_phone: "9876501234",
      support_email: "office@gv.example",
      status: 0,
      installed: 0,
      domain: "green-valley.eschool.example.com",
      domain_type: "default",
      domain_verified: 1,
    });
    expect(site).toMatchObject({ school_id: 12, name: "Green Valley Public School", slug: "green-valley", logo: "https://cdn.example.com/gv.png", phone: "9876501234", email: "office@gv.example", status: "pending_approval", setup_complete: false, custom_domain: null });
  });

  it("reads custom domains and their verification", () => {
    expect(slugOf({ domain: "portal.gv.edu", domain_type: "custom" })).toBe("");
    expect(siteFromSchool({ id: 1, name: "GV", domain: "portal.gv.edu", domain_type: "custom", domain_verified: 0 })).toMatchObject({ custom_domain: "portal.gv.edu", domain_status: "pending" });
    expect(siteFromSchool({ id: 1, name: "GV", domain: "portal.gv.edu", domain_type: "custom", domain_verified: 1 })).toMatchObject({ domain_status: "verified" });
  });
});

describe("public site before the backend can look schools up", () => {
  it("shows a neutral being-set-up page, never sample data", () => {
    render(<SiteBeingSetUp host="green-valley.eschool.example.com" loginUrl="/login" />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toMatch(/being set up/);
    expect(screen.queryByText(/Sample School/)).toBeNull();
  });
});
