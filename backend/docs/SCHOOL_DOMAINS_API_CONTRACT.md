# School domains and public school websites — API contract

admin-web has a **School domain** step in registration, a public school website served at
`{subdomain}.{root}` (or a verified custom domain), **Settings → Website & domain**, and a signed-in
**Preview my website** page (`/site-preview`).

## 0. Status (checked 26 Oct 2026 against main 4ab1c60 and Render)

Already in the backend (commit 12af540) and used by admin-web now:
- `POST /api/v1/schools/register` takes `domain_type: "default"` with the subdomain **prefix** in
  `domain` (stored as `{prefix}.{SCHOOL_BASE_DOMAIN or APP_URL host}`, `domain_verified=1`), or
  `domain_type: "custom"` with a full hostname (`domain_verified=0`). Domains are unique
  (409 "School domain already in use"). **Set `SCHOOL_BASE_DOMAIN` on Render** to the same value as
  admin-web's `NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN`; without it default domains fail with 500.
- `GET /school-admin/school` returns `domain`, `domain_type`, `domain_verified` (used by Settings and the preview).

**Still missing — needed for the public website to show each school's real data:**

1. **Public lookup (the one route that unblocks the website)**
   `GET /api/v1/public/schools/by-host?host={hostname}` — no auth, `Cache-Control: public, max-age=60`.
   - `host` = `{prefix}.{base}` → the school whose `domain` equals it (any status except deleted).
   - `host` = a custom domain → the school only when `domain_type = custom` **and** `domain_verified = 1`.
   - Otherwise `404 {"detail": "School not found"}`.
   - Response — safe fields only (no admin details, codes, tokens, billing):
     `{school_id, name, slug (the prefix), tagline, logo, address, city, phone (support_phone),
       email (support_email), theme_primary, theme_secondary, about, admissions_open,
       status: "pending_approval"|"active"|"inactive", setup_complete, custom_domain, domain_status}`
     Fields the backend doesn't have yet (city, theme, about, admissions_open) may be null/true.
   - Then admin-web sets `NEXT_PUBLIC_DOMAINS_API_MODE=live`.
2. `GET /api/v1/schools/subdomain-availability?slug=&name=&city=` (section 4) so registration can say
   "available" before submitting (today it relies on the 409).
3. Custom-domain verification + school-admin domain routes (section 6), and a school-admin
   `PATCH /school-admin/school` for name/logo/tagline/address/phone/email so admins can edit their website.

The sections below are the full proposal (some names differ from what was built: the backend stores
the full host in `domain` rather than separate `subdomain`/`custom_domain` columns — that's fine; the
public route above just needs to return the fields listed).

## 1. `schools` table — new columns

| Column | Type | Notes |
|---|---|---|
| `subdomain` | varchar(40), **unique** (case-insensitive), not null after backfill | Default site at `{subdomain}.{ROOT_DOMAIN}` |
| `domain_type` | varchar(10) `default` \| `custom` | What the admin chose at registration |
| `custom_domain` | varchar(253), unique (case-insensitive), nullable | e.g. `portal.greenvalleyschool.edu`; replaces today's free-text `domain` (migrate non-empty values here as `pending`) |
| `domain_status` | varchar(12) `not_started` \| `pending` \| `verified` \| `failed` | |
| `domain_verification_token` | varchar(64), nullable | Random, e.g. `eschool-verify-<24 hex>`; regenerate when the custom domain changes |
| `domain_verified_at`, `domain_checked_at` | timestamptz, nullable | |
| `domain_last_error` | varchar(255), nullable | Human-readable reason of the last failed check |
| `theme_primary`, `theme_secondary` | char(7) `#rrggbb`, nullable | Shown on the website; validated hex |
| `about` | text, nullable | About section of the website |
| `admissions_open` | boolean default true | |
| `city` | varchar(80), nullable | Registration already sends it; today it's merged into `address` |

Backfill `subdomain` for existing schools from `slugify(name)` with the duplicate rule below.

## 2. Subdomain rules (same as `admin-web/lib/domains/core.ts`)

- `slugify(name)`: Unicode-fold to ASCII, lowercase, `&` → `and`, every run of other characters → `-`,
  trim hyphens, max 40 characters (cut at a hyphen).
- Valid: `^[a-z0-9]+(-[a-z0-9]+)*$`, 3–40 characters, not all digits, not reserved:
  `www app admin api mail smtp imap pop ftp ns1 ns2 dns cdn static assets dashboard login register
  signup help support status blog docs billing school schools super-admin superadmin portal test dev
  staging localhost site by-host`.
- Duplicates get a **readable** alternative, in this order: `{slug}-{city}`, the name without filler
  words (the/of/and/school/academy/public/high/secondary/international/…), that plus `-{city}`,
  initials + `-{city}`, then `{slug}-2`, `{slug}-3`… The server is the final judge (unique index +
  retry inside the registration transaction).

## 3. Registration — `POST /api/v1/schools/register` (existing, extended)

New optional request fields (the model has `extra="forbid"`, so they must be added):

```json
{ "domain_type": "default" | "custom", "subdomain": "greenvalley", "custom_domain": "portal.greenvalleyschool.edu",
  "theme_primary": "#0f766e", "theme_secondary": "#f59e0b" }
```

- `subdomain` optional: if missing, generate from `name`. If given but taken → generate the next
  readable alternative instead of failing (or 409 `{"detail": "greenvalley.<root> is taken"}` — the
  frontend handles both).
- `custom_domain` required when `domain_type = custom`: hostname only (no scheme/path/port), valid
  labels, not on the platform root, not an IP, not `*.netlify.app`/`*.onrender.com`; unique (409
  `{"detail": "This custom domain is already used by another school."}`). Status starts `pending`.
- Today the frontend still sends the custom domain in the existing `domain` field; please treat
  `domain` as an alias of `custom_domain` until the frontend switches.
- Response adds:

```json
{ "school_id": 12, "status": "pending_approval", "message": "…",
  "subdomain": "greenvalley", "site_url": "https://greenvalley.<root>",
  "domain_verification": { "txt_name": "_eschool-verify.portal.greenvalleyschool.edu", "txt_value": "eschool-verify-…",
                           "cname_name": "portal.greenvalleyschool.edu", "cname_target": "greenvalley.<root>" } }
```

  (`domain_verification` is null for the default domain.) The website must work **immediately**,
  even while the school is `pending_approval`.

## 4. Subdomain availability (public, rate-limited)

`GET /api/v1/schools/subdomain-availability?slug=greenvalley&name=Green%20Valley%20Public%20School&city=Pune`

```json
{ "slug": "greenvalley", "available": false, "problem": "greenvalley.<root> is taken.", "suggestions": ["greenvalley-pune", "green-valley", "gv-pune"] }
```

Invalid slugs → `available: false` with the rule's message in `problem`.

## 5. Public school site lookup (no auth)

`GET /api/v1/public/schools/by-host?host=greenvalley.<root>` (also accepts a custom domain)

Returns **only** these fields (never ids of admins, emails of admins, tokens, status reasons, billing):

```json
{ "school_id": 12, "name": "Green Valley Public School", "slug": "greenvalley", "tagline": null, "logo": "https://…",
  "address": "…", "city": "Pune", "phone": "…", "email": "office@…", "theme_primary": "#0f766e", "theme_secondary": null,
  "about": null, "admissions_open": true, "status": "pending_approval|active|inactive", "setup_complete": false,
  "custom_domain": "portal.greenvalleyschool.edu", "domain_status": "pending" }
```

- `{subdomain}.{root}` → the school (any status except deleted).
- A custom domain → the school **only when `domain_status = verified`**; otherwise 404.
- Unknown host → 404 `{"detail": "School not found"}`.
- Cache-friendly (`Cache-Control: public, max-age=60`). `setup_complete` = approved + logo + about +
  phone/address (+ custom domain verified if chosen) — or your own definition.

## 6. School admin domain settings (auth: school admin, `settings.manage`)

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/school-admin/domain` | | `DomainSettings` |
| PATCH | `/school-admin/domain` | `{custom_domain: "…" \| null}` (and optionally `subdomain`, theme colours, about, admissions_open) | `DomainSettings` |
| POST | `/school-admin/domain/verify` | | `DomainSettings` after an immediate check |

```json
DomainSettings = { "slug": "greenvalley", "default_url": "https://greenvalley.<root>", "domain_type": "custom",
  "custom_domain": "portal.greenvalleyschool.edu", "domain_status": "pending",
  "verification": { "txt_name": "_eschool-verify.portal.greenvalleyschool.edu", "txt_value": "eschool-verify-…",
                    "cname_name": "portal.greenvalleyschool.edu", "cname_target": "greenvalley.<root>" },
  "last_checked_at": "2026-10-25T10:00:00Z", "last_error": "The TXT record wasn't found yet." }
```

**Verification**: TXT `_eschool-verify.{custom_domain}` must contain the token, **and** the domain must
CNAME (or A/ALIAS for apex domains) to `{subdomain}.{root}` / the hosting target. On success:
`verified`, `domain_verified_at`, and register the domain with the host (below). On failure keep
`pending` with `last_error` (after 72 h of failures → `failed`). A background job re-checks pending
domains (e.g. every 15 min for the first hour, then hourly, up to 72 h). Changing or removing the
domain resets the status and token.

## 7. CORS / hosts

- Allow `https://*.{ROOT_DOMAIN}` and every verified custom domain (or the public site makes no
  credentialed calls — it calls only `/public/...`, which can use `Access-Control-Allow-Origin: *`).
- New setting `SCHOOL_ROOT_DOMAIN` so links and `site_url` use the right root.

## 8. Hosting (platform owner, not code)

- Buy/choose the root domain, add wildcard DNS `*.{root}` (and `{root}`) pointing at the Netlify site.
- Netlify: wildcard subdomains need a **Pro** plan and a support request; set
  `NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN={root}` and `NEXT_PUBLIC_APP_URL=https://app.{root}` (or the root).
- Custom domains: each verified domain must be added to the Netlify site as a domain alias (Netlify API
  `PATCH /sites/{id}` `domain_aliases`, with a token stored on the backend), which also issues HTTPS.
  Alternatives: Cloudflare for SaaS (custom hostnames) in front of Netlify. Then set
  `NEXT_PUBLIC_SCHOOL_CUSTOM_DOMAINS=on` so the frontend routes custom hosts to school sites
  (until then unknown hosts always show the admin app).
