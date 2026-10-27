import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { appOrigin, routeForHost } from "@/lib/domains/core";

/**
 * Route guard for the v1 Bearer auth flow.
 * Presence cookie `v1_session` is set client-side after /api/v1/auth/login.
 * Public marketing pages stay open; admin modules require a session.
 */
const PUBLIC_PREFIXES = ["/", "/login"];

function isPublicPath(pathname: string): boolean {
  if (pathname === "/" || pathname === "/login" || pathname.startsWith("/login/")) {
    return true;
  }
  if (pathname === "/register-school" || pathname.startsWith("/register-school/")) {
    return true;
  }
  // Public school websites (also reached through their own hosts, see schoolSite below).
  if (pathname === "/site" || pathname.startsWith("/site/")) {
    return true;
  }
  // Allow hash-only marketing anchors when requested as bare paths later.
  return PUBLIC_PREFIXES.some((p) => p !== "/" && pathname.startsWith(p));
}

/**
 * A school's own host ({slug}.{root}, or a verified custom domain) serves only its public site;
 * /login there goes to the admin app. Returns null for the admin app's hosts.
 */
function schoolSite(request: NextRequest): NextResponse | null {
  const route = routeForHost(request.headers.get("x-forwarded-host") ?? request.headers.get("host"));
  if (route.kind === "app") return null;
  const { pathname } = request.nextUrl;
  if (pathname === "/login" || pathname.startsWith("/login/")) {
    const current = { protocol: request.nextUrl.protocol, port: request.nextUrl.port };
    const target = new URL(`${appOrigin(current)}/login`);
    if (route.kind === "school") target.searchParams.set("school", route.slug);
    return NextResponse.redirect(target);
  }
  if (pathname.startsWith("/site/")) return NextResponse.next();
  const url = request.nextUrl.clone();
  url.pathname = route.kind === "school" ? `/site/${route.slug}` : `/site/by-host/${encodeURIComponent(route.host)}`;
  return NextResponse.rewrite(url);
}

export function middleware(request: NextRequest) {
  const site = schoolSite(request);
  if (site) return site;
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get("v1_session")?.value);

  if (pathname === "/login/reset" || pathname.startsWith("/login/reset/")) {
    return NextResponse.next();
  }

  if (pathname === "/login" || pathname.startsWith("/login/")) {
    if (hasSession) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
    return NextResponse.next();
  }

  if (pathname === "/") {
    return NextResponse.next();
  }

  if (!hasSession && !isPublicPath(pathname)) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", pathname);
    return NextResponse.redirect(login);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/).*)"],
};
