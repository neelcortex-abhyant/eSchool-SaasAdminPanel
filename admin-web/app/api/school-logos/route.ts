import { NextRequest, NextResponse } from "next/server";
import { MAX_LOGO_BYTES, saveLogo } from "@/lib/schoolLogoStore";

const WINDOW_MS = 60 * 60 * 1000;
const MAX_UPLOADS = 20;
const uploads = new Map<string, number[]>();

function tooMany(request: NextRequest): boolean {
  const forwarded = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const ip = forwarded || "local";
  const now = Date.now();
  const recent = (uploads.get(ip) || []).filter((at) => now - at < WINDOW_MS);
  if (recent.length >= MAX_UPLOADS) {
    uploads.set(ip, recent);
    return true;
  }
  recent.push(now);
  uploads.set(ip, recent);
  return false;
}

export async function POST(request: NextRequest) {
  if (tooMany(request)) {
    return NextResponse.json({ detail: "Too many logo uploads. Try again later." }, { status: 429 });
  }

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return NextResponse.json({ detail: "Choose an image file." }, { status: 422 });
  }

  const file = form.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ detail: "Choose an image file." }, { status: 422 });
  }
  if (file.size <= 0 || file.size > MAX_LOGO_BYTES) {
    return NextResponse.json({ detail: "Logo image must be 2 MB or smaller." }, { status: 422 });
  }

  const bytes = Buffer.from(await file.arrayBuffer());
  const saved = await saveLogo(bytes);
  if (!saved) {
    return NextResponse.json({ detail: "Logo must be a PNG, JPEG, WEBP, or GIF image." }, { status: 422 });
  }
  return NextResponse.json({ logo: saved.logo }, { status: 201 });
}
