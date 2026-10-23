import { NextResponse } from "next/server";

export async function GET() {
  const backend = (
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    "https://eschool-backend-8322.onrender.com"
  ).replace(/\/$/, "");
  try {
    const upstream = await fetch(`${backend}/api/get-languages`, { next: { revalidate: 3600 } });
    const data = await upstream.json().catch(() => ({ data: [] }));
    // The language list rarely changes: cache it so every page load doesn't wait on the backend.
    const headers = upstream.ok ? { "Cache-Control": "public, max-age=300, stale-while-revalidate=86400" } : undefined;
    return NextResponse.json(data, { status: upstream.status, headers });
  } catch {
    return NextResponse.json({ data: [{ code: "en", name: "English" }] });
  }
}
