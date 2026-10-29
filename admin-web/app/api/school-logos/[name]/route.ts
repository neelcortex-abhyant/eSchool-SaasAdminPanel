import { NextResponse } from "next/server";
import { contentTypeFor, readLogo } from "@/lib/schoolLogoStore";

type Ctx = { params: Promise<{ name: string }> };

export async function GET(_request: Request, ctx: Ctx) {
  const { name } = await ctx.params;
  const bytes = await readLogo(name);
  if (!bytes) {
    return NextResponse.json({ detail: "Logo not found" }, { status: 404 });
  }
  return new NextResponse(new Uint8Array(bytes), {
    status: 200,
    headers: {
      "Content-Type": contentTypeFor(name),
      "Cache-Control": "public, max-age=86400",
    },
  });
}
