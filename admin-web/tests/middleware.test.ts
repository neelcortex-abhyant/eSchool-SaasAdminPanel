// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

async function run(url: string, host: string, cookie = "") {
  vi.resetModules();
  const { middleware } = await import("@/middleware");
  const request = new NextRequest(url, { headers: { host, ...(cookie ? { cookie } : {}) } });
  return middleware(request);
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("middleware host routing", () => {
  it("rewrites a school subdomain to its public site", async () => {
    vi.stubEnv("NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN", "eschool.example.com");
    const response = await run("https://greenvalley.eschool.example.com/", "greenvalley.eschool.example.com");
    expect(response.headers.get("x-middleware-rewrite")).toBe("https://greenvalley.eschool.example.com/site/greenvalley");
  });

  it("sends /login on a school subdomain to the app's login", async () => {
    vi.stubEnv("NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN", "eschool.example.com");
    const response = await run("https://greenvalley.eschool.example.com/login", "greenvalley.eschool.example.com");
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("https://eschool.example.com/login?school=greenvalley");
  });

  it("leaves the admin app alone and keeps its sign-in guard", async () => {
    vi.stubEnv("NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN", "eschool.example.com");
    const response = await run("https://eschool.example.com/school/students", "eschool.example.com");
    expect(response.headers.get("x-middleware-rewrite")).toBeNull();
    expect(response.headers.get("location")).toMatch(/\/login\?next=%2Fschool%2Fstudents$/);
  });

  it("lets anyone open /site pages without signing in", async () => {
    const response = await run("http://localhost:3000/site/greenvalley", "localhost:3000");
    expect(response.headers.get("location")).toBeNull();
  });

  it("routes a custom domain only when custom domains are on", async () => {
    vi.stubEnv("NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN", "eschool.example.com");
    vi.stubEnv("NEXT_PUBLIC_SCHOOL_CUSTOM_DOMAINS", "on");
    const on = await run("https://portal.school.edu/", "portal.school.edu");
    expect(on.headers.get("x-middleware-rewrite")).toBe("https://portal.school.edu/site/by-host/portal.school.edu");
    vi.stubEnv("NEXT_PUBLIC_SCHOOL_CUSTOM_DOMAINS", "");
    const off = await run("https://portal.school.edu/", "portal.school.edu");
    expect(off.headers.get("x-middleware-rewrite")).toBeNull();
  });
});
