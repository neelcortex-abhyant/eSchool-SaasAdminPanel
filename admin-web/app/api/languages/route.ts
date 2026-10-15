import { NextResponse } from "next/server";

export async function GET() {
  const backend = (
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    "https://eschool-backend-8322.onrender.com"
  ).replace(/\/$/, "");
  try {
    const upstream = await fetch(`${backend}/api/get-languages`, { cache: "no-store" });
    const data = await upstream.json().catch(() => ({ data: [] }));
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json({ data: [{ code: "en", name: "English" }] });
  }
}
