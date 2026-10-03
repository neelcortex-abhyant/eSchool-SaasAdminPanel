import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Redirect unauthenticated users to /login.
 * Cookie name matches FastAPI `/api/admin/login` (`eschool_session`).
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname === "/login" || pathname.startsWith("/login/")) {
    if (request.cookies.get("eschool_session")) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    return NextResponse.next();
  }

  if (!request.cookies.get("eschool_session")) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", pathname);
    return NextResponse.redirect(login);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Protect app routes; skip Next internals and public assets.
     * `/api/*` is rewritten to FastAPI and is not matched here.
     */
    "/((?!_next/static|_next/image|favicon.ico|api/).*)",
  ],
};
