/**
 * School domains: default subdomains made from the school name, custom domains, and which school a
 * request's host belongs to. Pure functions so the middleware (edge), pages and tests share them.
 */

/** The platform's root domain, e.g. "eschool.example.com". Schools get "{slug}.{root}". */
export function rootDomain(): string {
  return (process.env.NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN || "localhost").trim().toLowerCase().replace(/^\.+|\.+$/g, "");
}

/** Subdomains schools can't take: the platform's own hosts and common system names. */
export const RESERVED_SLUGS = new Set([
  "www", "app", "admin", "api", "mail", "smtp", "imap", "pop", "ftp", "ns1", "ns2", "dns", "cdn", "static", "assets",
  "dashboard", "login", "register", "signup", "help", "support", "status", "blog", "docs", "billing", "school", "schools",
  "super-admin", "superadmin", "portal", "test", "dev", "staging", "localhost", "site", "by-host",
]);

export const SLUG_MIN = 3;
export const SLUG_MAX = 40;

const STOP_WORDS = new Set(["the", "of", "and", "school", "schools", "academy", "public", "high", "higher", "secondary", "senior", "international", "convent", "vidyalaya", "college", "institute"]);

/** Lowercase ASCII letters, digits and single hyphens; accents folded ("São Paulo" → "sao-paulo"). */
export function slugify(name: string): string {
  const ascii = name
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  if (ascii.length <= SLUG_MAX) return ascii;
  // Cut at a word boundary: keep the last word if it ends exactly at the limit.
  const cut = ascii.slice(0, SLUG_MAX);
  if (ascii[SLUG_MAX] === "-") return cut.replace(/-+$/g, "");
  return cut.replace(/-+[^-]*$/, "").replace(/-+$/g, "") || cut;
}

/** Why a subdomain can't be used, or "" if it can. */
export function slugProblem(slug: string): string {
  if (!slug) return "Enter a subdomain.";
  if (slug.length < SLUG_MIN) return `Use at least ${SLUG_MIN} characters.`;
  if (slug.length > SLUG_MAX) return `Use at most ${SLUG_MAX} characters.`;
  if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(slug)) return "Use lowercase letters, numbers and single hyphens, starting and ending with a letter or number.";
  if (RESERVED_SLUGS.has(slug)) return `"${slug}" is reserved. Choose another name.`;
  if (/^\d+$/.test(slug)) return "Include at least one letter.";
  return "";
}

/** The default subdomain for a school name (a readable fallback when the name gives nothing usable). */
export function defaultSlug(name: string): string {
  const slug = slugify(name);
  if (!slugProblem(slug)) return slug;
  const padded = slug.length && slug.length < SLUG_MIN ? `${slug}-school` : slug;
  return slugProblem(padded) ? "" : padded;
}

/**
 * Readable alternatives when a subdomain is taken, best first:
 * add the city, a short form without filler words, the initials with the city, then -2, -3…
 */
export function slugAlternatives(slug: string, opts: { name?: string; city?: string } = {}, taken: (candidate: string) => boolean = () => false, count = 3): string[] {
  const city = slugify(opts.city ?? "");
  const words = slugify(opts.name ?? slug).split("-").filter(Boolean);
  const short = words.filter((word) => !STOP_WORDS.has(word)).join("-");
  const initials = words.map((word) => word[0]).join("");
  const candidates = [
    city && `${slug}-${city}`,
    short && short !== slug && short,
    short && city && short !== slug && `${short}-${city}`,
    initials.length >= 2 && city && `${initials}-${city}`,
    ...Array.from({ length: 20 }, (_, i) => `${slug}-${i + 2}`),
  ].filter((value): value is string => Boolean(value));
  const out: string[] = [];
  for (const candidate of candidates) {
    const trimmed = candidate.length > SLUG_MAX ? slugify(candidate) : candidate;
    if (out.includes(trimmed) || trimmed === slug || slugProblem(trimmed) || taken(trimmed)) continue;
    out.push(trimmed);
    if (out.length >= count) break;
  }
  return out;
}

/** Lowercase host without protocol, path, port or trailing dot, or "" if it isn't a domain name. */
export function normalizeDomain(input: string): string {
  let text = input.trim().toLowerCase();
  text = text.replace(/^[a-z][a-z0-9+.-]*:\/\//, "");
  text = text.split(/[/?#]/)[0];
  text = text.replace(/:\d+$/, "").replace(/\.$/, "");
  return text;
}

/** Why a custom domain can't be used, or "" if it can. */
export function customDomainProblem(input: string, root = rootDomain()): string {
  const raw = input.trim();
  if (!raw) return "Enter your domain, e.g. portal.yourschool.edu.";
  if (/^[a-z]+:\/\//i.test(raw) || /[/?#]/.test(raw.replace(/^[a-z]+:\/\//i, ""))) return "Enter only the domain, without http:// or a path.";
  const domain = normalizeDomain(raw);
  if (domain.length > 253) return "That domain is too long.";
  const labels = domain.split(".");
  if (labels.length < 2 || labels.some((label) => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label)) || !/^[a-z]{2,63}$/.test(labels[labels.length - 1])) {
    return "Enter a valid domain, e.g. portal.yourschool.edu.";
  }
  if (root && (domain === root || domain.endsWith(`.${root}`))) return `Use the default domain option for addresses on ${root}.`;
  if (/(^|\.)(localhost|netlify\.app|onrender\.com)$/.test(domain) || /^\d+(\.\d+){3}$/.test(domain)) return "Use a domain your school owns.";
  return "";
}

/** The full default address of a school. */
export function schoolHost(slug: string, root = rootDomain()): string {
  return `${slug}.${root}`;
}

export type HostRoute = { kind: "app" } | { kind: "school"; slug: string } | { kind: "custom"; host: string };

/** Extra hosts that serve the admin app (NEXT_PUBLIC_APP_HOSTS, comma-separated), e.g. the Netlify primary domain. */
export function appHosts(): string[] {
  return (process.env.NEXT_PUBLIC_APP_HOSTS || "").split(",").map((host) => normalizeDomain(host)).filter(Boolean);
}

/** Custom domains are routed only when NEXT_PUBLIC_SCHOOL_CUSTOM_DOMAINS=on, so an unknown host never hides the app. */
export function customDomainsEnabled(): boolean {
  return (process.env.NEXT_PUBLIC_SCHOOL_CUSTOM_DOMAINS || "").trim().toLowerCase() === "on";
}

/** Hosts that always serve the admin app, never a school site. */
function isAppHost(host: string, root: string, extra: string[]): boolean {
  if (extra.includes(host)) return true;
  if (!host || host === root || host === `www.${root}` || host === `app.${root}` || host === `admin.${root}`) return true;
  if (host === "localhost" || host === "127.0.0.1" || host === "[::1]" || /^\d+(\.\d+){3}$/.test(host)) return true;
  if (host.endsWith(".netlify.app") || host.endsWith(".netlify.com") || host.endsWith(".onrender.com")) return true;
  return false;
}

/**
 * Which site a host serves: the admin app, a school's default subdomain ({slug}.{root}), or a
 * custom domain (looked up by the server; served only once verified).
 */
export function routeForHost(
  hostHeader: string | null | undefined,
  root = rootDomain(),
  options: { customDomains?: boolean; appHosts?: string[] } = {},
): HostRoute {
  const host = normalizeDomain(hostHeader ?? "");
  if (isAppHost(host, root, options.appHosts ?? appHosts())) return { kind: "app" };
  if (host.endsWith(`.${root}`)) {
    const label = host.slice(0, -(root.length + 1));
    // Only one level ({slug}.{root}); deeper names and reserved labels stay on the app.
    if (label.includes(".") || slugProblem(label)) return { kind: "app" };
    return { kind: "school", slug: label };
  }
  return (options.customDomains ?? customDomainsEnabled()) ? { kind: "custom", host } : { kind: "app" };
}

/** The URL of a school's default site; on a local root the current port is kept so it opens in development. */
export function schoolSiteUrl(slug: string, root = rootDomain(), current?: { protocol: string; port: string }): string {
  const local = root === "localhost" || root.endsWith(".localhost") || root.endsWith(".test");
  const protocol = local ? current?.protocol ?? "http:" : "https:";
  const port = local && current?.port ? `:${current.port}` : "";
  return `${protocol}//${schoolHost(slug, root)}${port}`;
}

/** Where the admin app lives, for links from a school site (NEXT_PUBLIC_APP_URL, else the root domain). */
export function appOrigin(current?: { protocol: string; port: string }, root = rootDomain()): string {
  const configured = (process.env.NEXT_PUBLIC_APP_URL || "").trim().replace(/\/$/, "");
  if (configured) return configured;
  const local = root === "localhost" || root.endsWith(".localhost") || root.endsWith(".test");
  return `${local ? current?.protocol ?? "http:" : "https:"}//${root}${local && current?.port ? `:${current.port}` : ""}`;
}
