import { NextRequest, NextResponse } from "next/server";

/**
 * Forward browser same-origin /api/* calls to FastAPI (BACKEND_URL).
 * Used on Netlify where next.config rewrites to an external host are unreliable
 * and BACKEND_URL must be read at runtime (not only at build time).
 */
export async function proxyToBackend(
  request: NextRequest,
  segments: string[],
  apiPrefix: "/api/v1" | "/api/admin",
): Promise<NextResponse> {
  const backend = (
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    (process.env.NODE_ENV === "production"
      ? "https://eschool-backend-8322.onrender.com"
      : "http://127.0.0.1:8001")
  ).replace(/\/$/, "");
  const path = segments.map(encodeURIComponent).join("/");
  const target = `${backend}${apiPrefix}/${path}${request.nextUrl.search}`;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const authorization = request.headers.get("authorization");
  if (authorization) headers.set("authorization", authorization);
  const cookie = request.headers.get("cookie");
  if (cookie) headers.set("cookie", cookie);
  const accept = request.headers.get("accept");
  if (accept) headers.set("accept", accept);

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      {
        detail: `Cannot reach backend at ${backend}${apiPrefix}. Set BACKEND_URL on Netlify. (${message})`,
      },
      { status: 502 },
    );
  }

  const out = new Headers();
  const upstreamType = upstream.headers.get("content-type");
  if (upstreamType) out.set("content-type", upstreamType);

  // Node fetch may expose getSetCookie(); fall back to header when present.
  const anyHeaders = upstream.headers as Headers & { getSetCookie?: () => string[] };
  if (typeof anyHeaders.getSetCookie === "function") {
    for (const value of anyHeaders.getSetCookie()) {
      out.append("set-cookie", value);
    }
  } else {
    const setCookie = upstream.headers.get("set-cookie");
    if (setCookie) out.set("set-cookie", setCookie);
  }

  const body = await upstream.arrayBuffer();
  return new NextResponse(body, { status: upstream.status, headers: out });
}
