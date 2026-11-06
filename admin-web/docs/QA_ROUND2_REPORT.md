# QA round 2: frontend report (admin-web)

Branch `qa/branch-and-fixes`, 5 Nov 2026. Backend: Nitish's FastAPI on Render (OpenAPI 639 paths, unchanged since `42eaaee`).
No backend code was changed and nothing was written to Render. Walkthroughs ran against a local production build with a fake API.

**Status words:**
- **Done:** fixed and checked.
- **Verified:** the screen works against the backend's routes and a local fake API.
- **Needs live QA:** works locally; needs a run with real data on staging.
- **BLOCKED:** needs a backend change.

## Results

| Check | Result |
| --- | --- |
| Unit and component tests | 21 files, **173 / 173 pass** (5 new for this round) |
| Type check, production build | Pass; build has 0 warnings |
| Walkthrough (headless Chrome, production build) | **17 / 17 checks pass** (`qa-screenshots/results.json`) |
| School Admin menu routes | **124 / 124** open without a crash, error banner or horizontal scroll |
| Super Admin routes (menu + school create, view, edit, backups) | **18 / 18** clean |
| Responsive (dashboard 1366 / 768 / 375 px) | No horizontal scroll (screenshots 06–08) |

Screenshots are in [`docs/qa-screenshots/`](qa-screenshots/).

## 1. Confirmed bugs: Done

| Bug | Fix | Evidence |
| --- | --- | --- |
| **BUG-01** Registration preview showed `.localhost` | The preview uses `NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN`, `localhost` only in development, and otherwise just the address prefix. After registration it uses the server's `site_url`. The Website page uses the full host the backend saved in `school.domain`. | Test; screenshot `01-register-domain-preview.png` |
| **BUG-02** Terms and Privacy links went to Contact | New public pages `/terms` and `/privacy`, linked from registration (new tab) and the site footer; the sign-in guard leaves them open. | Tests; screenshots `02-terms.png`, `03-privacy.png` |
| **BUG-03** Class/section errors stayed after valid choices | A field's error clears when it changes; changing session or class clears its dependants. The same fix went into the parent and teacher/staff forms. | Test; screenshot `09-admission-errors-cleared.png` |

**Action needed for BUG-01:** pick the platform domain (for example `schoolsarthi.app`). Set `NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN` in `netlify.toml` and Nitish's `SCHOOL_BASE_DOMAIN` on Render to the same value. Until then the preview shows only the prefix (no fake domain).

**Action needed for BUG-02:** the Terms and Privacy text is a working draft in `lib/marketing/legal.ts`, and the pages say it's being finalised. It needs the business's approved wording; then set `LEGAL_DRAFT = false`. The backend has no platform legal-content route.

## 2. School and second branch: BLOCKED

The backend has no branch concept: no routes, table or `parent_school_id`. Branch screens were **not** built with browser-only data. The exact contract is in [BRANCH_API_CONTRACT.md](BRANCH_API_CONTRACT.md), covering Super Admin branch CRUD and admin assignment, branch switching by a scoped token, consolidated summary and reports, and the isolation rules.

The following are all BLOCKED:
- add/list/view/edit/disable/delete branch
- Branch Admin assignment and screens
- branch switching
- branch-specific records and dashboards
- consolidated reports
- branch permission hiding
- "Branch 1 unchanged after Branch 2 operations"

Existing school information (Super Admin school list, profile, create, edit) is **Verified** (routes clean; screenshots `super-schools*.png`).

## 3. Student admission and management

| Item | Status |
| --- | --- |
| Admission form validation | **Done** (BUG-03). Required fields are checked before sending, and server 422 field errors show on the right fields. |
| Class → section dropdown dependency | **Verified**: section is disabled until a class is chosen, and changing class resets section. |
| Student create, profile view and edit | **Verified** (`/students`, `/students/{id}`, PATCH). Needs live QA with real data. |
| Search, status filter, pagination | **Verified** (server-side `q`, `status`, `page`, max 50). |
| Duplicate admission number | Shown from the server's 409/422 message on the admission number field. **Needs live QA.** |
| Success and failure notifications | **Verified** (toasts; form-level error). |
| Student in attendance, fees and other modules | **Needs live QA** (same student IDs across modules). |
| Saved in the correct branch | **BLOCKED** (branches). |

## 4. Fees and finance

| Item | Status |
| --- | --- |
| Installment due date | **Verified**: native date input, server dates trimmed to `YYYY-MM-DD`, required and no two installments on the same day. |
| Fee structure create/edit and installments | **Verified** (`/fee-structures`, PUT installments). |
| Student fee assignment, concessions, outstanding | **Verified** (`/fee-assignments`, `/fee-concessions`, `/fees/outstanding`). |
| Manual collection, receipt, history | **Verified** (`/fees/collect` with an idempotency key, `/fee-payments/{id}/receipt` and PDF, cancel). **Needs live QA** for amounts. |
| Dashboard collection totals | **Done**: School dashboard now shows "Fees collected this month" (`/fees/collection-report`) and "Fees pending" (`/fees/outstanding` summary). |
| Contradictory assignment guidance | **Done to match the backend**: on the server a student owes a structure only once it's assigned (no automatic class assignment), and the page now says so. **Needs a business-rule decision:** if classes should be assigned automatically, Nitish must add it (e.g. assign on admission or a bulk "assign to class" route). |
| Inconsistent payment-storage messages | **Done**: the dashboard said "Collected fee payments are not stored", which is wrong because payments are stored. Replaced. |
| Duplicate payment submissions | **Verified**: one submit at a time (`useSubmitOnce`) plus an idempotency key. |
| Branch-wise financial records | **BLOCKED** (branches). |

## 5. Authentication and roles

| Item | Status |
| --- | --- |
| School registration screen | **Verified** (BUG-01/02 fixed). Needs live QA for the confirmation email. |
| Login, logout, invalid credentials | **Verified** (`/auth/login`, `/auth/logout`; the server's message is shown). |
| Forgot / reset password | **Verified** (`/auth/forgot-password`, `/login/reset` → `/auth/reset-password`). Needs live QA with a real email. |
| Profile editing, change password | **Verified** (`/users/me` PATCH, `/auth/change-password`). |
| Super Admin vs School Admin navigation | **Verified**: separate menus, and school admins are kept inside `/school/*`. |
| Protected pages and expired sessions | **Verified**: signed-out users go to `/login?next=…` (screenshot 04), and a 401 leads to "Your session has expired" (05). |
| Role and permission APIs | **Verified** (`/super-admin/roles`, `/permissions`, `/school-admin/staff-roles`, `/staff/{user_id}/roles`). |
| Branch Admin screens and restrictions | **BLOCKED** (branches). |
| Teacher / Student / Parent interfaces | Out of scope for admin-web (Flutter apps). |

## 6. Academics

**Verified** (routes open; create/edit forms against the backend routes; duplicates shown from server errors):
- classes (search, medium filter), sections, subjects, teacher assignments
- attendance marking and history
- offline exams (papers, marks, process results, publish)
- timetable, homework (attachments download through the signed-in API), notices and announcements

**Needs live QA:** the save/read round trips with real data.

## 7. Dashboard, reports and navigation

| Item | Status |
| --- | --- |
| School dashboard counts | **Done**: students, classes, subjects, exams and (new) teachers, plus fee totals. |
| Reports & analytics, sidebar routes | **Verified** (124 + 18 routes clean). |
| Back/forward, reload | **Verified** (walkthrough). |
| Empty, loading and error states | **Verified**. Fixed this round: 17 status lookups could crash a page on an unknown status (e.g. Online exams). They now show a grey chip with the raw value. |
| Branch dashboards, consolidated reports | **BLOCKED** (branches). |

## 8. Notifications and API

**Verified:**
- registration confirmation screen
- password-reset screens
- payment success and pending messages
- notification delivery status (queued/sent/partial/failed/cancelled, with cancel and refresh)
- duplicate-request guards
- request/response shapes checked against the OpenAPI

**Not wired on purpose:** fee reminders, because the backend sends them to every parent (see `NOTE_FOR_NITISH_FINAL_BACKEND.md`).

## 9–10. UI and frontend security

| Item | Status |
| --- | --- |
| Responsive at 1366 / 768 / 375 px | **Verified**: no horizontal scroll on any swept route (desktop) or the dashboard (all three widths). |
| Browsers | Chrome **Verified**. Safari, Firefox and Edge are **not run** (need a manual pass). |
| Forms, required fields, modals, confirmations, disabled buttons, double-click | **Verified** (shared `FormModal`, `ConfirmDialog`, `useSubmitOnce`). |
| Role-based menus, restricted screens, expired sessions, unauthorized API answers | **Verified** (tests + walkthrough). |
| Server errors shown safely | **Verified**: only the server's `detail` text or a plain fallback, never stack traces or tokens. |
| Backend authorization and branch isolation | **Nitish** (backend); branch isolation is BLOCKED. |

## 11. End-to-end flows

| Flow | Status |
| --- | --- |
| School registration → login → dashboard | Screens **Verified**; needs live QA for the full round trip (it creates a real school). |
| Existing school → add Branch 2 → assign admin → switch | **BLOCKED** |
| Branch 2 → class → section → student | **BLOCKED** (the same flow without branches is Verified) |
| Branch 2 → teacher → subjects | **BLOCKED** (Verified without branches) |
| Admission → fee assignment → payment → receipt | Screens **Verified**; **needs live QA** |
| Admission → attendance → exam → results | Screens **Verified**; **needs live QA** |
| Branch Admin login → own branch | **BLOCKED** |
| School Admin → both branches → consolidated reports | **BLOCKED** |
| Edit Branch 2 → Branch 1 unchanged | **BLOCKED** |
| Logout → protected URL → login | **Done** (walkthrough + test) |
| Three confirmed bugs resolved | **Done** |

## 12. Missing APIs and backend items (for Nitish)

1. **Branches:** everything in [BRANCH_API_CONTRACT.md](BRANCH_API_CONTRACT.md).
2. **Platform domain:** set `SCHOOL_BASE_DOMAIN` (and the panel's `NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN`). Optional: `GET /public/platform` → `{school_base_domain}` so the panel reads it from the server.
3. **Fee assignment rule:** if a class's structure should apply to all its students, add automatic or bulk assignment (e.g. `POST /fee-structures/{id}/assign-class`).
4. **Platform legal content (optional):** `GET /public/content/{terms|privacy}` if the text should be edited from Super Admin instead of the code.
5. Still open from `NOTE_FOR_NITISH_FINAL_BACKEND.md`:
   - notification targeting
   - migrations 0044/0045
   - certificate PDF placeholders
   - ID card PDF and bulk generation
   - report filters and exports
   - attendance edit/lock
   - logo storage
   - custom-domain routes
   - PATCH for stops and concessions

## Pending or out of scope

- Safari, Firefox and Edge passes.
- Live-data QA on a staging school for the flows marked "needs live QA" (not run here, since nothing may be created on Render).
- Approved legal text.
- The platform domain decision.

## Ready for another QA round?

**Yes, for everything except branches.** All implemented frontend workflows pass locally and match the backend's routes. Branch work starts once the branch API exists.
