import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Route guard for the v1 Bearer auth flow.
 * Presence cookie `v1_session` is set client-side after /api/v1/auth/login.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get("v1_session")?.value);

  if (pathname === "/login" || pathname.startsWith("/login/")) {
    if (hasSession) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    return NextResponse.next();
  }

  if (!hasSession) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", pathname);
    return NextResponse.redirect(login);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|api/).*)",
  ],
};
