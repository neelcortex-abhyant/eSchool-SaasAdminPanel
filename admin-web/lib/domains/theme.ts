/** School theme colours with readable text: falls back to the platform colours when missing or invalid. */
export const DEFAULT_PRIMARY = "#0f766e";
export const DEFAULT_SECONDARY = "#f59e0b";

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

export function luminance(hex: string): number {
  const n = parseInt(hex.slice(1), 16);
  return 0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255);
}

export function contrast(a: string, b: string): number {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}

/** White or black text, whichever reads better on the colour (at least 4.5:1 for any colour but a few mid-greys). */
export function textOn(hex: string): string {
  return contrast(hex, "#ffffff") >= contrast(hex, "#000000") ? "#ffffff" : "#000000";
}

const VALID = /^#[0-9a-f]{6}$/i;

export function siteTheme(primary: string | null | undefined, secondary: string | null | undefined) {
  const p = primary && VALID.test(primary) ? primary.toLowerCase() : DEFAULT_PRIMARY;
  const s = secondary && VALID.test(secondary) ? secondary.toLowerCase() : DEFAULT_SECONDARY;
  return { primary: p, onPrimary: textOn(p), secondary: s, onSecondary: textOn(s) };
}

/** Setup steps shown to the school's admin; the site says "being set up" until all are done. */
export function setupSteps(site: { status: string; logo: string | null; about: string | null; phone: string | null; address: string | null; custom_domain: string | null; domain_status: string }) {
  return [
    { key: "approved", label: "Platform approval", done: site.status === "active" },
    { key: "logo", label: "Upload the school logo", done: Boolean(site.logo) },
    { key: "about", label: "Write the About section", done: Boolean(site.about) },
    { key: "contact", label: "Add the phone number and address", done: Boolean(site.phone && site.address) },
    ...(site.custom_domain ? [{ key: "domain", label: `Connect ${site.custom_domain}`, done: site.domain_status === "verified" }] : []),
  ];
}

export function setupIncomplete(site: Parameters<typeof setupSteps>[0] & { setup_complete: boolean }): boolean {
  return !site.setup_complete || setupSteps(site).some((step) => !step.done);
}
