import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ExtrasPage } from "@/components/extras/Frame";
import { api, invalidateApiCache, SESSION_EXPIRED_EVENT } from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/school/reports",
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

afterEach(cleanup);

function answer(status: number, body: unknown = {}) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })));
}

beforeEach(() => {
  invalidateApiCache();
  window.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("expired sessions", () => {
  it("announces an expired session when the server refuses the saved token", async () => {
    window.localStorage.setItem("v1_access_token", "old-token");
    const heard = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, heard);
    answer(401, { detail: "Not authenticated" });
    await api("/school-admin/students");
    window.removeEventListener(SESSION_EXPIRED_EVENT, heard);
    expect(heard).toHaveBeenCalledTimes(1);
  });

  it("doesn't treat a wrong password or a signed-out request as an expired session", async () => {
    const heard = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, heard);
    answer(401, { detail: "Invalid email or password" });
    window.localStorage.setItem("v1_access_token", "old-token");
    await api("/auth/login", { method: "POST", body: "{}" });
    window.localStorage.clear();
    await api("/school-admin/students");
    window.removeEventListener(SESSION_EXPIRED_EVENT, heard);
    expect(heard).not.toHaveBeenCalled();
  });
});

describe("school admin pages", () => {
  it("show a sign-in link instead of the page when the session has expired", async () => {
    window.localStorage.setItem("v1_access_token", "old-token");
    answer(401, { detail: "Not authenticated" });
    render(
      <ExtrasPage title="Reports" icon={null}>
        <p>Secret report</p>
      </ExtrasPage>,
    );
    expect(await screen.findByRole("link", { name: /sign in/i })).toBeTruthy();
    expect(screen.queryByText("Secret report")).toBeNull();
  });

  it("refuse users who aren't school admins", async () => {
    window.localStorage.setItem("v1_access_token", "super-token");
    answer(403, { detail: "Forbidden" });
    render(
      <ExtrasPage title="Reports" icon={null}>
        <p>Secret report</p>
      </ExtrasPage>,
    );
    expect(await screen.findByText("Only school admins can open this page.")).toBeTruthy();
    expect(screen.queryByText("Secret report")).toBeNull();
  });
});
