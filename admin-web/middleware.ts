import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

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
  // Allow hash-only marketing anchors when requested as bare paths later.
  return PUBLIC_PREFIXES.some((p) => p !== "/" && pathname.startsWith(p));
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get("v1_session")?.value);

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
