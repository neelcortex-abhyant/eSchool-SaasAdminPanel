# Admin app foundation

How the admin app (`admin-web`, Next.js 15 App Router) is put together, and how to add a module.
The theme is the approved one: a cream page, white cards, amber primary actions and charcoal text, with Inter at a 14px base.

## Structure

```
app/
  (admin)/layout.tsx        every admin page renders inside AdminShell (sidebar + header)
  (admin)/dashboard, schools, plans, subscriptions, payments, …   Super Admin pages
  (admin)/school/…          School Admin pages; /school/[module] serves menu slugs (registry)
  login/, site/, register-school/   public pages (middleware leaves them open)
components/
  ui/                       shared UI, imported from "@/components/ui" (list below)
  AdminShell.tsx            layout: sidebar, top header, content; session-expiry redirect
  layout/Sidebar.tsx, TopHeader.tsx
  schools/, payments/, dashboard/, …   feature components (one folder per area)
lib/
  api.ts                    the only fetch wrapper (auth, cache, errors, 401 handling)
  nav.ts                    navigation config for both roles
  school.ts, payments.ts, … service modules: one per area, typed, no JSX
  icons.tsx                 inline SVG icons
app/globals.css             tokens (:root) and all styles
middleware.ts               sign-in guard and school-site host routing
```

## Tokens (`app/globals.css`, `:root`)

| Group | Tokens |
| --- | --- |
| Colour | `--color-bg` (cream), `--color-surface`, `--color-border(-strong)`, `--color-text(-muted, -subtle)`, `--color-primary` (amber) `-hover` `-ink` `-soft`, `--color-on-primary`, `--color-accent`, `--color-success/warning/danger` (+ `-soft`) |
| Type | `--text-2xs` 11 · `--text-xs` 12 · `--text-sm` 13 · `--text-base` 14 · `--text-md` 16 · `--text-lg` 18 · `--text-xl` 22 · `--text-2xl` 28 (page title); `--weight-regular/medium/semibold/bold`; `--leading-tight/normal` |
| Spacing | `--space-1` 4 · `-2` 8 · `-3` 12 · `-4` 16 · `-5` 20 · `-6` 24 · `-8` 32 · `-10` 40 · `-12` 48 |
| Shape | `--radius-sm` 10 · `-md` 14 · `-lg` 18 · `-pill`; `--shadow-sm`, `--shadow-md` |
| Layout | `--sidebar-width` 260, `--sidebar-collapsed` 76, `--header-height` 64, `--content-narrow` 760 |

**Breakpoints:** phone ≤ 600px, tablet ≤ 900px (the sidebar becomes a drawer), narrow desktop ≤ 1100px.
CSS variables can't be used inside `@media`, so write these numbers. Tables turn into labelled cards on phones (each `<td data-label>`).

Dark mode is set with `html[data-theme="dark"]` (the header toggle). Use the tokens rather than fixed colours so new styles follow it.

## Shared components (`@/components/ui`)

| Component | Use |
| --- | --- |
| `PageHeading` | Super Admin page title row: `icon`, `title`, `description`. |
| `Button`, `ButtonLink`, `buttonClass()` | Variants `primary` (amber), `secondary`, `danger`, `link`, `link-danger`. `busy` disables the button and can swap in `busyLabel`. |
| `Card` | White panel with an optional `title` and `actions`. |
| `DataTable`, `Pagination`, `Column` | Lists: columns with `render`, row `actions`, a loading skeleton, empty text and sort headers. On phones, rows become cards. |
| `TextField`, `SelectField`, `TextAreaField`, `StatusToggle` | Form fields with label, hint, error and `required`. |
| `FormModal` | Add/edit dialog with error banner, saving state and a submit label. |
| `ConfirmDialog` | Confirmation before deleting or changing status; the body may be text or a field. |
| `Chip`, `Stat`, `StatusBadge` | Status pill (green/amber/red/grey/blue), count card, active/inactive badge. |
| `LinkTabs`, `ButtonTabs` | Tabs as links (one page per tab) or as buttons (same page). |
| `EmptyState`, `Skeleton` | Nothing-to-show message with an optional action; loading placeholder. |
| `ErrorAlert` | Load error with Retry, or Sign in when the session expired. |
| `ToastProvider`, `useToast` | `toast("success" \| "error", text)` after saves. |
| `useOptions`, `usePagedList`, `useFormErrors`, `useDebounced` | Data hooks: load a list, a page, server field errors, a debounced search. |

School Admin pages wrap their content in `ExtrasPage` / `AcademicPage` / `TeachingPage`. These add the header, tabs, the school-admin access check and toasts.

## API layer

- **`lib/api.ts`** is the only place that calls `fetch`. `api<T>(path, init)` returns `{ ok, status, data }` and:
  - adds the Bearer token;
  - shares identical GETs and caches them for 30 s (any write clears the cache);
  - retries once against Render on a 5xx from the proxy;
  - on a 401 with a token (except sign-in), fires `v1:session-expired`, and AdminShell clears the session and opens `/login?expired=1&next=…`.

  It also has `apiErrorMessage(data, fallback)` (FastAPI `detail` → text) and `apiBlobUrl(path)` (signed-in file downloads).
- **Service modules** (`lib/<area>.ts`) hold every route for an area, with types. Pages call these, never URLs. For example, `lib/school.ts` has:
  - `loadSchools`, `loadSchool`, `loadSchoolAdmins`
  - `saveSchool(body, id?)` (POST to create, PATCH to edit)
  - `setSchoolStatus(id, "activate" | "suspend" | "deactivate" | "provision")`
  - `deleteSchool`, `addSchoolAdmin`
- **Backend:** Nitish's FastAPI on Render. List routes return `{items, total, page, page_size}`, with `page_size` at most 50. The browser calls `NEXT_PUBLIC_ADMIN_API_URL`, and on Netlify it goes straight to Render. Production settings are in `netlify.toml` (repo root).

## School pages (Super Admin)

| Page | Route | Pieces |
| --- | --- | --- |
| Schools list | `/schools` | `PageHeading`, filters, table, `ConfirmDialog` → `loadSchools`, `setSchoolStatus` |
| Create school | `/schools/new` | `SchoolForm mode="create"` → `saveSchool`, `setSchoolStatus` (if inactive), `addSchoolAdmin` |
| Edit school | `/schools/[id]/edit` | `SchoolForm mode="edit"` → `loadSchool`, `saveSchool(…, id)`, `setSchoolStatus` on a status change |
| School profile | `/schools/[id]` | `PageHeading`, details, admins, billing, payment history → `loadSchool`, `loadSchoolAdmins`, `setSchoolStatus`, `deleteSchool` |

Validation and the request body live in `lib/schoolForm.ts` (`validateSchool`, `schoolRequestBody`, server field errors).

## Adding a module

1. **Service:** add `lib/<area>.ts` with types and one function per route, using `api()`.
2. **Page:** add `app/(admin)/<route>/page.tsx` (Super Admin) or `app/(admin)/school/<route>/page.tsx` (School Admin). For a simple list or settings screen on a school-admin route, add a config to `lib/extras/pages.ts` instead; the `/school/[module]` registry renders it.
3. **UI:** build from `@/components/ui`: `PageHeading` or a page frame, `DataTable` + `Pagination`, `FormModal` + fields, `ConfirmDialog` for destructive actions, `useToast` after saves, and `ErrorAlert` for load errors.
4. **Navigation:** add a link in `lib/nav.ts` (`NAV_ITEMS` for Super Admin, `SCHOOL_ADMIN_NAV` for School Admin). The sign-in guard covers new routes automatically.
5. **Styles:** add CSS to `app/globals.css` with the tokens. Check widths of 375, 768 and 1366px for no horizontal scroll.
6. **Tests:** add `tests/<area>.test.tsx` (Vitest + Testing Library; stub `fetch`, as `tests/foundation.test.tsx` does). Run `npm test`, `npx tsc --noEmit` and a production build.
