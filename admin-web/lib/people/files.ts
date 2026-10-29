/**
 * Upload limits. The browser checks these first for a quick message; the server repeats every
 * check (type sniffed from the file bytes, not the name) because the browser can be bypassed.
 */
export const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const PHOTO_MAX_BYTES = 2 * 1024 * 1024;
export const DOCUMENT_TYPES = ["application/pdf", "image/jpeg", "image/png"];
export const DOCUMENT_MAX_BYTES = 5 * 1024 * 1024;
export const DOCUMENTS_PER_RECORD = 10;

export const PHOTO_ACCEPT = ".jpg,.jpeg,.png,.webp";
export const DOCUMENT_ACCEPT = ".pdf,.jpg,.jpeg,.png";

const EXTENSION_TYPES: Record<string, string> = {
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  webp: "image/webp",
  pdf: "application/pdf",
};

/** The browser's type, or one from the extension when the browser leaves it empty. */
export function fileType(file: File): string {
  if (file.type) return file.type;
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  return EXTENSION_TYPES[extension] ?? "";
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Returns a message for a file that can't be used as a profile photo, or "" when it's fine. */
export function photoProblem(file: File): string {
  if (!PHOTO_TYPES.includes(fileType(file))) return "Use a JPG, PNG or WebP image.";
  if (file.size > PHOTO_MAX_BYTES) return `The photo is ${formatBytes(file.size)}. The limit is ${formatBytes(PHOTO_MAX_BYTES)}.`;
  if (file.size === 0) return "This file is empty.";
  return "";
}

/** Returns a message for a file that can't be uploaded as a document, or "" when it's fine. */
export function documentProblem(file: File): string {
  if (!DOCUMENT_TYPES.includes(fileType(file))) return `${file.name} isn't a PDF, JPG or PNG file.`;
  if (file.size > DOCUMENT_MAX_BYTES) return `${file.name} is ${formatBytes(file.size)}. The limit is ${formatBytes(DOCUMENT_MAX_BYTES)}.`;
  if (file.size === 0) return `${file.name} is empty.`;
  return "";
}

/** "birth-certificate_2026.pdf" → "birth certificate 2026", used as the default document title. */
export function titleFromFileName(name: string): string {
  const base = name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim();
  return base ? base.charAt(0).toUpperCase() + base.slice(1) : "Document";
}
