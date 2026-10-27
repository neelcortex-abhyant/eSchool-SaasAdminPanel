import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { useState } from "react";
import { DomainStep, EMPTY_DOMAIN, typedSlug, type DomainCheck } from "@/components/domains/DomainStep";
import { SchoolLanding } from "@/components/domains/SchoolLanding";
import type { SchoolSite } from "@/lib/domains/types";

afterEach(cleanup);

const minimal: SchoolSite = {
  school_id: 9,
  name: "Green Valley Public School",
  slug: "greenvalley",
  tagline: null,
  logo: null,
  address: null,
  city: null,
  phone: null,
  email: null,
  theme_primary: null,
  theme_secondary: null,
  about: null,
  admissions_open: true,
  status: "pending_approval",
  setup_complete: false,
  custom_domain: null,
  domain_status: "not_started",
};

describe("SchoolLanding", () => {
  it("renders with only a name: hero, sections, login and the setup notice", () => {
    render(<SchoolLanding site={minimal} loginUrl="https://app.example/login?school=greenvalley" appUrl="https://app.example" />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Welcome to Green Valley Public School");
    for (const name of ["About us", "Admissions & enrolment", "Contact"]) expect(screen.getByRole("heading", { name })).toBeTruthy();
    expect(screen.getByRole("status").textContent).toMatch(/being set up/);
    expect(screen.getAllByRole("link", { name: /login/i })[0].getAttribute("href")).toBe("https://app.example/login?school=greenvalley");
    expect(screen.getAllByText("Coming soon")).toHaveLength(2);
    expect(screen.queryByText(/Finish setup/)).toBeNull();
  });

  it("uses the school's details and hides the setup notice when setup is complete", () => {
    const full: SchoolSite = { ...minimal, status: "active", setup_complete: true, logo: "/logo.png", about: "We teach.", phone: "+91 98765 43210", address: "12 MG Road", city: "Pune", email: "office@gv.example", theme_primary: "#1d4ed8" };
    const { container } = render(<SchoolLanding site={full} loginUrl="/login" appUrl="" />);
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByText("We teach.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "+91 98765 43210" }).getAttribute("href")).toBe("tel:+919876543210");
    expect((container.firstChild as HTMLElement).style.getPropertyValue("--site-primary")).toBe("#1d4ed8");
  });
});

function Harness() {
  const [value, setValue] = useState(EMPTY_DOMAIN);
  const [check, setCheck] = useState<DomainCheck>({ state: "idle", result: null, message: "" });
  return <DomainStep name="Green Valley Public School" city="Pune" value={value} onChange={setValue} check={check} onCheck={setCheck} errors={{}} />;
}

describe("DomainStep", () => {
  it("proposes a subdomain from the name and shows the custom domain field when chosen", () => {
    const { container } = render(<Harness />);
    expect((container.querySelector("#reg-subdomain") as HTMLInputElement).value).toBe("green-valley-public-school");
    fireEvent.click(screen.getByLabelText(/Custom domain/));
    expect(screen.getByLabelText(/Your domain/)).toBeTruthy();
    expect(screen.getByText(/created now/)).toBeTruthy();
  });

  it("keeps typed subdomains to valid characters", () => {
    expect(typedSlug("Green Valley!")).toBe("green-valley-");
    expect(typedSlug("--São")).toBe("sao");
  });
});
