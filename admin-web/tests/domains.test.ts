import { describe, expect, it } from "vitest";
import { customDomainProblem, defaultSlug, normalizeDomain, routeForHost, slugAlternatives, slugify, slugProblem } from "@/lib/domains/core";
import { cleanSite } from "@/lib/domains/sites";
import { contrast, setupIncomplete, siteTheme, textOn } from "@/lib/domains/theme";

describe("slugify and defaultSlug", () => {
  it("makes readable subdomains from school names", () => {
    expect(slugify("Green Valley Public School")).toBe("green-valley-public-school");
    expect(slugify("  St. Mary's Convent & High School ")).toBe("st-mary-s-convent-and-high-school");
    expect(slugify("Escola São Paulo")).toBe("escola-sao-paulo");
    expect(slugify("A".repeat(60))).toHaveLength(40);
    expect(slugify("The International School of Business and Technology, Bengaluru")).toBe("the-international-school-of-business-and");
  });

  it("falls back sensibly for short or empty names", () => {
    expect(defaultSlug("AB")).toBe("ab-school");
    expect(defaultSlug("学校")).toBe("");
    expect(defaultSlug("Admin")).toBe("");
  });
});

describe("slugProblem", () => {
  it("accepts good slugs and explains bad ones", () => {
    expect(slugProblem("greenvalley")).toBe("");
    expect(slugProblem("ab")).toMatch(/at least 3/);
    expect(slugProblem("green--valley")).toMatch(/single hyphens/);
    expect(slugProblem("-green")).toMatch(/single hyphens/);
    expect(slugProblem("www")).toMatch(/reserved/);
    expect(slugProblem("12345")).toMatch(/letter/);
  });
});

describe("slugAlternatives", () => {
  it("offers city, short and initials forms before numbers, skipping taken ones", () => {
    const taken = new Set(["greenvalley-pune"]);
    expect(slugAlternatives("green-valley-public-school", { name: "Green Valley Public School", city: "Pune" }, (s) => taken.has(s))).toEqual([
      "green-valley-public-school-pune",
      "green-valley",
      "green-valley-pune",
    ]);
    expect(slugAlternatives("greenvalley", { name: "Greenvalley", city: "Pune" }, (s) => taken.has(s))).toEqual(["greenvalley-2", "greenvalley-3", "greenvalley-4"]);
  });
});

describe("customDomainProblem", () => {
  it("accepts a school's own domain", () => {
    expect(customDomainProblem("portal.greenvalleyschool.edu", "eschool.example.com")).toBe("");
    expect(customDomainProblem("GreenValley.EDU.in", "eschool.example.com")).toBe("");
  });

  it("refuses protocols, paths, the platform root and bad names", () => {
    expect(customDomainProblem("https://portal.school.edu", "eschool.example.com")).toMatch(/without http/);
    expect(customDomainProblem("portal.school.edu/home", "eschool.example.com")).toMatch(/without http/);
    expect(customDomainProblem("x.eschool.example.com", "eschool.example.com")).toMatch(/default domain/);
    expect(customDomainProblem("school", "eschool.example.com")).toMatch(/valid domain/);
    expect(customDomainProblem("-bad-.edu", "eschool.example.com")).toMatch(/valid domain/);
    expect(customDomainProblem("10.0.0.1", "eschool.example.com")).toMatch(/valid domain|owns/);
    expect(customDomainProblem("myschool.netlify.app", "eschool.example.com")).toMatch(/owns/);
  });

  it("normalises hosts", () => {
    expect(normalizeDomain("HTTPS://Portal.School.EDU:443/path?x")).toBe("portal.school.edu");
  });
});

describe("routeForHost", () => {
  const root = "eschool.example.com";
  const cases: [string, ReturnType<typeof routeForHost>][] = [
    ["eschool.example.com", { kind: "app" }],
    ["www.eschool.example.com", { kind: "app" }],
    ["app.eschool.example.com", { kind: "app" }],
    ["greenvalley.eschool.example.com", { kind: "school", slug: "greenvalley" }],
    ["GreenValley.eschool.example.com:443", { kind: "school", slug: "greenvalley" }],
    ["a.b.eschool.example.com", { kind: "app" }],
    ["api.eschool.example.com", { kind: "app" }],
    ["schoolsarthi.netlify.app", { kind: "app" }],
    ["localhost:3000", { kind: "app" }],
    ["127.0.0.1", { kind: "app" }],
  ];
  it.each(cases)("%s → %o", (host, expected) => {
    expect(routeForHost(host, root, { customDomains: true, appHosts: [] })).toEqual(expected);
  });

  it("routes custom hosts only when custom domains are switched on, and never app hosts", () => {
    expect(routeForHost("portal.school.edu", root, { customDomains: true, appHosts: [] })).toEqual({ kind: "custom", host: "portal.school.edu" });
    expect(routeForHost("portal.school.edu", root, { customDomains: false, appHosts: [] })).toEqual({ kind: "app" });
    expect(routeForHost("admin.schoolsarthi.com", root, { customDomains: true, appHosts: ["admin.schoolsarthi.com"] })).toEqual({ kind: "app" });
  });

  it("supports greenvalley.localhost in development", () => {
    expect(routeForHost("greenvalley.localhost:3000", "localhost", { customDomains: false, appHosts: [] })).toEqual({ kind: "school", slug: "greenvalley" });
  });
});

describe("theme and setup", () => {
  it("keeps text readable on any school colour", () => {
    expect(textOn("#0f766e")).toBe("#ffffff");
    expect(textOn("#fde68a")).toBe("#000000");
    for (const colour of ["#000000", "#ffffff", "#ff0000", "#00ff00", "#0000ff", "#f59e0b"]) {
      expect(contrast(colour, textOn(colour))).toBeGreaterThanOrEqual(4.5);
    }
    expect(siteTheme("red", "#12345")).toMatchObject({ primary: "#0f766e", secondary: "#f59e0b" });
  });

  it("shows the setup banner until every step is done", () => {
    const base = { status: "active", logo: "/logo.png", about: "About", phone: "1", address: "A", custom_domain: null, domain_status: "not_started", setup_complete: true };
    expect(setupIncomplete(base)).toBe(false);
    expect(setupIncomplete({ ...base, status: "pending_approval" })).toBe(true);
    expect(setupIncomplete({ ...base, custom_domain: "portal.x.edu", domain_status: "pending" })).toBe(true);
    expect(setupIncomplete({ ...base, setup_complete: false })).toBe(true);
  });
});

describe("cleanSite", () => {
  it("drops unsafe or invalid profile values", () => {
    const site = cleanSite({ name: " Green Valley ", slug: "greenvalley", logo: "javascript:alert(1)", email: "not-an-email", theme_primary: "blue", status: "weird", domain_status: "nope" });
    expect(site).toMatchObject({ name: "Green Valley", logo: null, email: null, theme_primary: null, status: "pending_approval", domain_status: "not_started", admissions_open: true });
    expect(cleanSite({ slug: "x" })).toBeNull();
  });
});
