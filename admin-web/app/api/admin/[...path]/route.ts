import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backendProxy";

type Ctx = { params: Promise<{ path: string[] }> };

async function handle(request: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxyToBackend(request, path ?? [], "/api/admin");
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
export const OPTIONS = handle;
