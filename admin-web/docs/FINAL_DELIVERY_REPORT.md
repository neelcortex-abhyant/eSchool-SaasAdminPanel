# Final delivery report — eSchool SaaS Admin Panel

Branch `release/final-integration` · 30 Oct 2026 · frontend `admin-web` (Next.js 15) against
Nitish's FastAPI backend on Render. Only the backend's existing routes are used; no backend code
was changed and no data was created on Render.

Status words: **Done** = built and verified as described; **Partial** = works, with a stated
limit; **BLOCKED** = needs a backend change (see the dependency report in
[INTEGRATION_CHECKLIST.md](INTEGRATION_CHECKLIST.md)); **Not run** = a check that still needs a person.

## Results at a glance

| Check | Result |
| --- | --- |
| Unit and component tests (`npm test`) | 18 files, 155 tests, all pass |
| Type check (`tsc --noEmit`) | Passes |
| Production build (`next build` with the Netlify environment) | Passes, no warnings; 103 kB shared first-load JS |
| API mapping | 247 paths and 108 write calls matched to the backend's OpenAPI (624 paths, 30 Oct). Only gaps: the custom-domain routes (BLOCKED, D-2) |
| Responsive sweep (local fake backend) | 24 School Admin and 14 Super Admin pages × 375 / 768 / 1366 px (114 loads): no horizontal scroll; 2 page crashes and 3 React key warnings found and fixed (below) |
| Console | No `console.*` or `debugger` in app code; no console errors on the swept pages after the fixes |
| Live data on Render | **Not run.** Needs a school-admin login; read-only smoke test listed below |

## Module 1 — Reports & analytics — Done

New page `/school/reports` (menu: Reports › Reports & analytics) with tabs for Students,
Academics, Finance, Staff and Transport. The tab is kept in the address (`?category=`), so a
report can be bookmarked or shared.

- **Filters:** from/to dates with quick ranges (this month, last 3 or 6 months, this year);
  session, class and section on Students, Academics and Finance. Staff and Transport say the
  class filters don't apply. A backwards date range is explained and not sent.
- **Students:** totals, active/inactive, admitted in the period, attendance rate; students by
  class (chart), admissions by month (trend); class/section table with attendance; attendance
  summary; server enrollment status.
- **Academics:** exams, results processed, passed/failed, pass rate, average score; average by
  class and by subject (charts); exam results, class-wise and subject-wise tables.
- **Finance:** collected in the period, outstanding, overdue, all-time income/expenses/net;
  monthly collection trend; payment-method chart and table; 50 largest balances.
- **Staff:** staff and teachers, attendance rate, leave requests and pending leave, payroll for
  the year; staff by department; monthly net payroll; attendance, leave-by-type, payroll and
  employment tables.
- **Transport:** routes, vehicles, students on transport, trips and boarding rate in the period;
  students by route and boarding rate by route; routes, attendance-by-route and vehicle tables.
- **Export:** CSV of every table in the current report (spreadsheet formulas neutralised);
  Print / PDF prints a clean report (menus and filters hidden, title with the dates).
- **States:** skeleton while loading; the previous report stays visible while the next loads;
  empty text per chart and table; if one source fails, the rest still shows with a note naming
  the part that failed; if everything fails, an error with Retry (or Sign in when expired).
- **Data:** each report uses the backend's report routes where they exist and the same services
  as the rest of the panel; breakdowns the server doesn't group are counted in the browser and
  each tab says so. Only the signed-in admin's school is read (the server scopes by token).

## Module 2 — API integration and verification — Done (with BLOCKED items)

- Mapping checked route by route against the OpenAPI; see [INTEGRATION_CHECKLIST.md](INTEGRATION_CHECKLIST.md)
  for every Super Admin and School Admin module, its routes, data source and how it was verified.
- Fixed in this pass:
  - **Offline exams:** editing and removing a subject paper now uses the server's new
    `PATCH/DELETE /offline-exam-schedules/{id}` (it was hidden as "not on the server").
  - **Operations modules** (bus tracking, leave, payroll, messages, notices, certificates) now
    use the routes from backend migration 0043 by default. This includes vehicle locations,
    leave types and balances, student leave, payslip PDF, staff certificates, the issued
    certificate list and revoke, and announcement audience/status.
  - **Teacher and staff profiles** use the documents now included in the profile response,
    saving one request per profile.
  - **Menu:** "Assign roll number" and "Upload profile images" led to an empty placeholder.
    They are now working pages, built on `PATCH /students/{id}` and `POST /students/{id}/photo`.
    "Database backup" has no backend route, so it was removed from the menu (D-5).
- Permissions: the sign-in guard on every admin URL and the school-admin check on every School
  Admin page (403 → "Only school admins can open this page") are covered by tests. The shell
  also keeps school admins inside `/school/*` and `/settings`.

## Module 3 — Performance and UI — Done

- **Lazy loading:** the 30 custom screens under `/school/[module]` (payroll, messages, ID
  cards, imports…) now load on demand. First-load JS for that route fell from 206 kB to 160 kB
  (route chunk 50.6 kB → 14.8 kB). The bus map was already lazy.
- **Fewer API calls:**
  - Student details for fee reports, receipts and outstanding lists come from the paged
    student list (50 per request) when more than 25 are needed, instead of one request per
    student.
  - Identical GETs share one request and are reused for 30 s.
  - Profiles reuse the documents included in their response.
- **Large tables:** lists page on the server (50 max); report tables cap at sensible sizes
  (50 balances, 20 exams) and say so; charts show 12 bars and point to the table.
- **Expired sessions:** any signed-in request answered 401 (except sign-in itself) clears the
  session and opens `/login?expired=1&next=…` with "Your session has expired". After signing in
  the admin returns to the same page. The `next` value now only accepts same-site paths.
- **Robustness:** an unknown status from the server (payslips, announcements, notifications)
  showed a blank page; it now falls back safely. Department lists are de-duplicated. A payment
  without a gateway no longer adds an empty choice to the gateway filter, and roles without a
  key are skipped.
- **Duplicate submits:** fee collection and payroll processing send idempotency keys. Payment
  cancel, messages and notices ignore a second click while saving. Other forms, including the
  new roll-number save, disable their button while pending.
- **Failed requests:** lists keep their rows and show the server's message with Retry; partial
  failures are reported per part (reports, bulk roll numbers, bulk photos).
- **Responsive:** no horizontal scroll at 375, 768 or 1366 px on the swept pages; tables turn
  into labelled cards on phones; report charts stack to one column.
- **Clean-up:** removed the unused leave-types page (`LeaveConfigPage`) and its imports. No
  unused source files remain. Dependencies are already minimal: next, react, react-dom, leaflet.

## Module 4 — Testing and production readiness

| Item | Status |
| --- | --- |
| Functional tests (reports, operations, fees, grading, transport, people, academics, domains, forms) | Done — 155 passing |
| Route guards and permissions (middleware, school-admin gate, expired session) | Done — `tests/middleware.test.ts`, `tests/session.test.tsx` |
| Responsive check at 375 / 768 / 1366 px | Done on the local fake backend (School Admin and Super Admin pages) |
| Production build | Done — passes with the Netlify environment |
| Environment and production URLs | Done — `netlify.toml` points at Render; **`NEXT_PUBLIC_OPS_API_MODE = "live"` was missing and is added in this change** (without it fees, grading, transport and two report tabs show sample data) |
| No debug logs or console errors | Done for app code and swept pages |
| Live smoke test on Render with a school admin and a super admin | **Not run** — needs your login; steps below |

### Live smoke test (read-only, about 15 minutes)

1. Deploy this branch to a Netlify preview, then sign in as a school admin.
2. Reports & analytics: open each tab for the last 6 months. Export a CSV and print one report.
3. Open students, fees › payments, offline exams, payroll › payslips, announcements, bus
   tracking and certificate assign. Each should show the school's own data with no red errors.
4. Sign in as the super admin and open schools, subscriptions, payments and reports.
5. In the browser storage, remove `v1_access_token`, then click any menu item. You should land
   on sign-in with "Your session has expired".

## Known issues and limits

| # | Issue | Status |
| --- | --- | --- |
| D-1 | School logos are stored on the Next.js server's disk; on Netlify that isn't permanent, so uploaded logos can disappear after a deploy | **BLOCKED** — needs a backend logo route |
| D-2 | Custom domains can't be connected or verified | **BLOCKED** — `/school-admin/domain` routes missing |
| D-3 | Student attendance can't be corrected or locked and has no Leave status. The list has no filters, so the Students report reads up to 1,000 attendance rows | **BLOCKED** / Partial |
| D-4 | A transport stop, a student's transport and a fee concession can't be edited (remove and add again) | **BLOCKED** |
| D-5 | Database backup | **BLOCKED** — removed from the menu |
| D-6 | Report breakdowns are computed in the browser; very large schools may load slowly | Partial — server aggregates would help |
| — | Reports were checked against a local fake backend and stubbed tests, not against real school data on Render | Pending the live smoke test |
| — | `origin/main` removed `admin-web` again in `ce89003`. Merging this branch into main must keep `admin-web`, or Netlify (base `admin-web`) will fail | Needs your decision at merge time |

## What changed (uncommitted, awaiting your approval)

- **New:**
  - `app/(admin)/school/reports/page.tsx`, `components/reports/ReportsDashboard.tsx`,
    `lib/reports/analytics.ts`
  - `components/extras/StudentBulk.tsx`, `components/operations/PdfDownload.tsx`
  - `tests/reports.test.tsx`, `tests/session.test.tsx`, `tests/student-bulk.test.tsx`
  - `docs/INTEGRATION_CHECKLIST.md`, `docs/FINAL_DELIVERY_REPORT.md`
- **Changed:**
  - `lib/api.ts`, `components/AdminShell.tsx`, `app/login/LoginForm.tsx` (expired sessions)
  - `components/extras/registry.tsx` (lazy loading, new pages)
  - `lib/nav.ts`, `lib/ops/lookups.ts`, `lib/people/http.ts`, `lib/teaching/offline.ts`
  - `app/(admin)/payments/page.tsx`, `app/(admin)/school-admins/page.tsx` (filter fixes)
  - operations modules (`lib/operations/*`, `components/operations/*`), `lib/extras/*`
  - `app/globals.css`, tests
  - `netlify.toml` at the repo root (adds `NEXT_PUBLIC_OPS_API_MODE`)
- **Not to be committed:** `admin-web/tsconfig.tsbuildinfo` (build cache) and `admin-web/data/`
  (local test uploads).
