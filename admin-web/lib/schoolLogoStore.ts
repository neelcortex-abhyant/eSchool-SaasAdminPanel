import { randomUUID } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

export const LOGO_DIR = path.join(process.cwd(), "data", "school-logos");
export const MAX_LOGO_BYTES = 2 * 1024 * 1024;
export const LOGO_NAME =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(png|jpg|webp|gif)$/i;

const MIME: Record<string, string> = {
  png: "image/png",
  jpg: "image/jpeg",
  webp: "image/webp",
  gif: "image/gif",
};

export type LogoKind = "png" | "jpg" | "webp" | "gif";

export function sniffImage(buf: Buffer): LogoKind | null {
  if (buf.length >= 8 && buf[0] === 0x89 && buf.toString("ascii", 1, 4) === "PNG") return "png";
  if (buf.length >= 3 && buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) return "jpg";
  const head = buf.length >= 6 ? buf.toString("ascii", 0, 6) : "";
  if (head === "GIF87a" || head === "GIF89a") return "gif";
  if (buf.length >= 12 && buf.toString("ascii", 0, 4) === "RIFF" && buf.toString("ascii", 8, 12) === "WEBP") return "webp";
  return null;
}

export function logoFilePath(name: string): string | null {
  if (!LOGO_NAME.test(name)) return null;
  const root = path.resolve(LOGO_DIR);
  const full = path.resolve(root, name);
  if (full !== path.join(root, name)) return null;
  return full;
}

export async function saveLogo(bytes: Buffer): Promise<{ name: string; logo: string } | null> {
  const kind = sniffImage(bytes);
  if (!kind) return null;
  const name = `${randomUUID()}.${kind}`;
  await mkdir(LOGO_DIR, { recursive: true });
  await writeFile(path.join(LOGO_DIR, name), bytes);
  return { name, logo: `/api/school-logos/${name}` };
}

export function contentTypeFor(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() || "";
  return MIME[ext] || "application/octet-stream";
}

export async function readLogo(name: string): Promise<Buffer | null> {
  const full = logoFilePath(name);
  if (!full) return null;
  try {
    return await readFile(full);
  } catch {
    return null;
  }
}
