# Integration checklist — eSchool SaaS Admin Panel

Branch `release/final-integration`, 30 Oct 2026. Backend: Nitish's FastAPI on Render
(`https://eschool-backend-8322.onrender.com/api/v1`, OpenAPI with 639 paths, fetched 30 Oct 2026 after Nitish's
`42eaaee` "Backend gap closure" was deployed).
No new backend routes were created for this work; the frontend only calls routes that exist in that spec.

## How each item was verified

| Mark | Meaning |
| --- | --- |
| **API** | Every route the page calls was matched (path and method) against the backend's OpenAPI by `pathcheck.py` (247 paths and 108 write calls; 0 unexplained mismatches). |
| **Test** | Covered by the Vitest suite (stubbed API answers shaped like the backend's schemas). 19 files, 164 tests, all passing. |
| **UI** | Opened in the browser against a local fake backend (no data created on Render) at 375, 768 and 1366 px: renders, no horizontal scroll, no console errors. 38 pages, 114 loads. |
| **BLOCKED** | Needs a backend change; listed in the dependency report at the end. |

"Live" means the page reads and writes the backend in production (`netlify.toml` sets the API mode flags; see *Environment* below).

## Super Admin

| Module | Pages | Backend routes | Source | Verified |
| --- | --- | --- | --- | --- |
| Sign-in, session, password | `/login`, `/login/reset`, `/settings/password` | `/auth/login`, `/auth/me`, `/auth/change-password`, `/auth/forgot-password`, `/auth/reset-password` | Live | API · Test · UI |
| Dashboard | `/dashboard` | `/super-admin/dashboard`, `/dashboard/stats` (cards incl. teachers), `/dashboard/registrations?year=` (chart, by year), `/dashboard/subscriptions` (schools by plan), `/dashboard/recent-activities`, `/dashboard/recent-schools`, `/super-admin/payments` (recent payments), `/payments/summary` | Live | API · Test · UI |
| Schools | `/schools`, `/schools/new`, `/schools/[id]`, `/schools/[id]/edit` | `/super-admin/schools` (CRUD), `/{id}/activate|suspend|deactivate|provision`, `/{id}/admins` | Live | API · Test |
| School logo upload | school form, settings, registration | `/api/school-logos` (Next.js route, local disk) | **BLOCKED** in production | see D-1 |
| School admins | `/school-admins` (+ new, edit, roles) | `/super-admin/school-admins`, `/super-admin/schools/{id}/admins/{admin_id}` (+ `/status`, `/roles`, `/invite`), `/super-admin/roles`, `/super-admin/permissions` | Live (falls back to sample only if the routes are missing) | API · Test |
| Plans / packages | `/plans`, `/plans/new`, `/plans/[id]`, `/plans/[id]/edit`, `/packages` | `/super-admin/plans` (CRUD, `/status`) | Live | API · Test |
| Subscriptions | `/subscriptions`, `/subscriptions/assign`, `/subscriptions/[schoolId]`, `/renew` | `/super-admin/subscriptions`, `/super-admin/schools/{id}/subscriptions` (+ `/status`, `/renew`, `/renewals`, `/bills`) | Live; "Expire ended subscriptions" calls `/super-admin/subscriptions/expire-due` (nothing runs it automatically) | API |
| Payments and invoices | `/payments`, `/payments/[id]` | `/super-admin/payments`, `/super-admin/invoices`, `/super-admin/invoices/{id}/pdf` | Live | API |
| Add-ons | `/addons` | `/super-admin/addons` (list, create, PATCH name/description/price, status), `/super-admin/schools/{id}/addons` (+ `/status`) | Live | API |
| Reports | `/reports` | `/super-admin/reports/schools`, `/reports/subscriptions`, `/reports/bills` | Live | API |
| Audit logs | `/audit-logs` | `/super-admin/audit-logs` | Live | API |
| Platform backups | `/backups` | `/super-admin/backups` (list, start), `/super-admin/backups/{id}/restore` (typed RESTORE) | Live; the server only writes a record and only records a restore request, and the page says so | API · Test · UI |
| Notifications | `/announcements` | `/super-admin/notifications` | Live | API · Test |
| Settings | `/settings` | `/super-admin/settings` | Live | API |

## School Admin

| Module | Pages | Backend routes (under `/school-admin` unless shown) | Source | Verified |
| --- | --- | --- | --- | --- |
| **Reports & analytics (new)** | `/school/reports?category=students|academics|finance|staff|transport` | `/reports/students`, `/reports/staff`, `/reports/financial-summary`, `/fees/collection-report`, `/fees/outstanding`, `/staff-attendance/reports`, `/payroll/summary`, `/offline-exams` + `/{id}/results`, `/academics/attendances`, `/students`, `/staff`, `/teachers`, `/academics/leaves`, `/leave-types`, `/transport-routes`, `/vehicles`, `/transport-trips` | Live | API · Test · UI |
| Dashboard | `/school` | `/school-admin/academics/summary`, `/school-admin/school` | Live | API · UI |
| Academic setup | sessions, classes, sections, subjects, mediums, teacher assignments | `/school-admin/academics/{resource}` (GET/POST/PATCH/DELETE), `/sessions/{id}/activate` | Live | API · Test |
| Students, parents | `/school/students/*`, `/school/parents/*` | `/students` (CRUD, `/status`, `/guardians`, `/photo`, `/documents` + `/download`), `/parents` (+ `/status`) | Live | API · Test · UI |
| Teachers, staff | `/school/teachers/*`, `/school/staff/*` | `/teachers`, `/staff` (+ `/departments`, `/status`, `/photo`, `/documents`, `/staff/{user_id}/roles`) | Live | API · Test · UI |
| Student tools | promote, transfer, reset password, electives, bulk import | `/students/promote`, `/students/{id}/transfer`, `/students/{id}/reset-password`, `/students/{id}/electives`, `/students/import`, `/teachers/import`, `/staff/import` | Live | API · Test |
| **Assign roll numbers (new)** | `/school/assign-roll-number` | `GET/PATCH /school-admin/students/{id}` | Live | API · Test |
| **Upload profile photos (new)** | `/school/upload-profile-images` | `POST /school-admin/students/{id}/photo` | Live | API |
| Timetable | `/school/timetable/*` | `/timetable-entries`, `/timetable/weekly`, `/teachers/{id}/availability`, `/teachers/{id}/timetable/weekly` | Live | API · Test · UI |
| Student attendance | `/school/attendance/*` | `/school-admin/academics/attendances` (list, create) | Live; corrections, locks and the Leave status **BLOCKED** (D-3) | API · Test · UI |
| Homework, study materials | `/school/homework/*`, `/school/study-materials` | `/homework` (+ `/attachments`, `/submissions`, `/summary`), `/homework-submissions/{id}/evaluation`, `/study-materials` | Live | API · Test |
| Offline exams, marks, results | `/school/offline-exams/*` | `/offline-exams*`, `/offline-exam-schedules*` (now incl. PATCH/DELETE of a paper), `/offline-exam-marks*`, `/process-results`, `/results`, `/results/summary` | Live | API · Test · UI |
| Online exams, question bank | `/school/online-exams/*` | `/online-assessments` (+ `/questions`, `/questions/import`, `/attempts`), `/online-assessment-questions/{id}`, `/online-assessment-attempts/{id}`, `/question-bank`, `/online-assessments/{id}/questions/from-bank` (copy picked bank questions in one request) | Live | API · Test |
| Grading, report cards | `/school/grading`, `/school/report-cards/*` | `/grading-scales`, `/report-cards` (+ `/{id}/pdf`) | Live (with `NEXT_PUBLIC_OPS_API_MODE=live`) | API · Test |
| Fees | types, structures, assignments, concessions, collect, payments, receipts, outstanding, collection report | `/fee-types`, `/fee-structures`, `/fee-assignments`, `/fee-concessions`, `/fee-payments` (+ `/{id}/cancel`, `/{id}/receipt`, `/{id}/receipt/pdf`), `/fees/collect`, `/fees/outstanding`, `/fees/collection-report` | Live (with `NEXT_PUBLIC_OPS_API_MODE=live`); editing a concession **BLOCKED** (D-4) | API · Test · UI |
| Income and expenses | categories, entries, dashboard, reports | `/incomes`, `/incomes/dashboard`, `/income-categories`, `/academics/expenses`, `/expense-categories`, `/reports/income`, `/reports/expenses` | Live | API · Test |
| Transport | vehicles, routes and stops, student transport | `/vehicles`, `/transport-routes`, `/transport-stops`, `/student-transport-assignments` | Live (with `NEXT_PUBLIC_OPS_API_MODE=live`); editing a stop or an assignment **BLOCKED** (D-4) | API · Test · UI |
| Bus tracking, trips, transport attendance | `/school/transport/tracking|trips|boarding|reports` | `/transport/vehicle-locations`, `/transport-trips` (+ `/{id}` for one trip, `/start`, `/complete`, `/gps`, `/attendance`), `/transport/reports/trips` | Live | API · Test · UI |
| Staff attendance | mark, today, register, reports, QR settings | `/staff-attendance` (+ `/today`, `/register`, `/reports`), `/staff-qr-attendance-settings` | Live | API · Test · UI |
| Leave | staff leave, student leave, leave settings | `/academics/leaves` (list, create, DELETE), `/academics/leaves/{id}/approve`, `/reject`, `/cancel` (pending leave only; PATCH no longer changes status), `/leave-types` (CRUD, applies to staff/teachers/students/everyone), `/leave-balances`, `/leave-settings` | Live | API · Test · UI |
| Payroll | salary components, structures, process, payslips (+ PDF), reports, runs, settings | `/salary-components`, `/salary-structures`, `/salary-assignments`, `/payroll/preview`, `/payroll/process`, `/payslips` (+ `/pdf`), `/payroll/summary`, `/payroll-runs` (list), `/payroll-runs/{id}/mark-paid`, `/payroll/audit-events`, `/payroll-settings` | Live. Runs are created only by processing payroll (the server refuses typed-in amounts) | API · Test · UI |
| Announcements, notifications | `/school/announcement`, `/school/notification` | `/announcements` (GET/POST/PATCH/DELETE, audience, publish_at, status), `/notifications` (audience, delivery incl. cancelled), `/notifications/{id}` (refresh status), `/notifications/{id}/cancel` (queued only) | Live | API · Test · UI |
| Teacher–parent messages | `/school/messages` | `/messaging/policy`, `/conversations` (+ `/messages`, `/read`), `/conversations/unread-count`, `/conversations/attachments/upload` (up to 3 files a message), `/messages/{id}/attachments?storage_key=` (download), `/messages/{id}` | Live; attachments need document storage configured on the server | API · Test · UI |
| Certificates, ID cards | templates, assign/issue, issued list, revoke, PDF; student/staff/bulk ID cards, settings | `/certificate-templates`, `/certificates` (+ `/issue`, `/issue-staff`, `/{id}/pdf`, `/{id}/revoke`), `/id-card-settings`, `/students/{id}/id-card`, `/staff/{id}/id-card` | Live | API · Test · UI |
| Website and CMS | sliders, gallery, FAQs, content pages, contact inquiries | `/sliders`, `/gallery`, `/faqs`, `/content/{slug}`, `/contact-inquiries`, `/admission-inquiries` | Live | API · Test |
| Custom domain | `/school/website` | `/public/schools/by-host` (exists), `/school-admin/domain` (missing) | Subdomain live; custom domain **BLOCKED** (D-2) | API · Test |
| Settings | general, session year, payment gateway, email/WhatsApp templates, online exam terms, additional fields | `/school-admin/school`, `/payment-gateway-settings`, `/email-templates`, `/whatsapp-settings`, `/online-exam-terms`, `/user-form-fields` | Live | API · Test |
| Subscription, plans, add-ons (school view) | `/school/subscription`, `/school/plans`, `/school/addons` | `/subscription/plans`, `/subscription/addons`, `/schools/{id}/invoices` (+ `/pdf`), `/schools/{id}/payments` | Live | API |
| Support | `/school/support` | `/support-tickets` (+ `/{id}/messages`) | Live | API · Test |
| Database backup | — | none | Removed from the menu; **BLOCKED** (D-5) | — |

## Cross-cutting checks

| Check | Result |
| --- | --- |
| Sign-in guard (middleware) | Every admin URL sends a signed-out visitor to `/login?next=…`; signed-in users skip the sign-in page; public and reset pages stay open. Tested. |
| Role guard | School-admin pages call `/school-admin/me`; a 403 shows "Only school admins can open this page" (tested). The shell also keeps a school admin inside `/school/*` and `/settings`. |
| Expired session | Any signed-in request answered 401 (not sign-in itself) clears the session and returns to `/login?expired=1&next=…` with "Your session has expired". Tested. |
| School scoping | No school id is sent from the browser; the backend scopes `/school-admin/*` to the token's school. |
| Duplicate submits | Fee collection and payroll processing send an idempotency key; those, payment cancel, messages and notices go through `useSubmitOnce` (a second click is ignored while saving); other forms disable their button while pending. `useSubmitOnce` is tested. |
| Failed requests | Lists keep their old rows on a failed reload and show the server's message with Retry; reports show which parts failed and still show the rest. Tested. |
| Unknown values from the server | Payroll, announcement and notification statuses outside the known set no longer break the page (fixed in this pass). |
| Secrets | No tokens, passwords or keys in the frontend; only `NEXT_PUBLIC_*` URLs and mode flags. |

## Environment (production)

`netlify.toml` (repo root) must set:

```
NEXT_PUBLIC_ADMIN_API_URL = "https://eschool-backend-8322.onrender.com/api/v1"
NEXT_PUBLIC_BACKEND_URL   = "https://eschool-backend-8322.onrender.com"
BACKEND_URL               = "https://eschool-backend-8322.onrender.com"
NEXT_PUBLIC_ACADEMICS_API_MODE = "live"
NEXT_PUBLIC_PEOPLE_API_MODE    = "students:live,parents:live,teachers:live,staff:live"
NEXT_PUBLIC_TEACHING_API_MODE  = "live"
NEXT_PUBLIC_OPS_API_MODE       = "live"   # added in this pass
```

`NEXT_PUBLIC_OPERATIONS_API_MODE` defaults to live for every feature and needs no setting.
Without `NEXT_PUBLIC_OPS_API_MODE=live`, grading, fees and transport (and the Finance and Transport
reports) show sample data kept in the browser.

## Pending backend dependency report

| # | Needed from the backend | Affects | Today |
| --- | --- | --- | --- |
| D-1 | A route to upload and serve school logos (e.g. `POST /super-admin/schools/{id}/logo`, `POST /school-admin/school/logo`) | School create/edit, school settings, self-registration | Logos are saved to the Next.js server's disk, which isn't permanent on Netlify: uploads may fail or disappear after a deploy. |
| D-2 | `GET/PATCH /school-admin/domain` and `POST /school-admin/domain/verify` (see `backend/docs/SCHOOL_DOMAINS_API_CONTRACT.md`) | Custom domains on `/school/website` | Subdomains work; connecting a custom domain shows "not available yet". |
| D-3 | Attendance: PATCH for `attendances` (the generic route refuses it: "This record cannot be edited here"), a Leave status, lock/unlock, and date/class filters on `GET /academics/attendances` | Attendance corrections and locks; Student report attendance on big schools | Corrections, locks and Leave are hidden. The list has no filters, so the frontend reads every page (capped at 1,000 rows) and filters itself. |
| D-4 | PATCH for `/transport-stops/{id}`, `/student-transport-assignments/{id}`, `/fee-concessions/{id}` | Editing a stop, a student's transport, a concession | The page asks the admin to remove and add again. |
| D-5 | A real database backup (`/super-admin/backups` writes a metadata-only record: "full pg_dump against Neon is not wired"; restore only records the request) | School settings › Database backup; super-admin Backups | School menu item removed. The super-admin Backups page is connected and shows the server's own status and note, so nobody takes a record for a copy. |
| D-6 | Server-side report aggregates by class/section/subject/month (optional; performance) | Reports & analytics | Breakdowns are computed in the browser from the server's lists; fine for typical schools, slower for very large ones. |
| D-7 | Notification recipients: fee reminders (`POST /fees/send-reminders`), student absence and leave decisions are addressed to whole roles (all parents/students, all staff/teachers), with the student number and amount in the text | Fee reminders; automatic notices after marking absence or deciding leave | **Not wired**: no fee-reminder button. Absence and leave notices are created by the server and stay queued until Firebase credentials are set; targeting must be fixed before that. |
| D-8 | Migrations `0044` and `0045` applied on Neon (Nitish's report says they aren't, while the code using them is live) | Leave decisions, notifications, payroll runs, message attachments | Not verifiable without a login; part of the live smoke test. |

## Backend update 42eaaee (30 Oct 2026)

| New route | Used by |
| --- | --- |
| `POST /academics/leaves/{id}/approve`, `/reject`, `/cancel` | Staff leave and student leave (fixes approval, which the old PATCH can no longer do) |
| `GET /conversations/unread-count` | Messages: the unread figure covers every conversation, not only the filtered list |
| `POST /conversations/attachments/upload`, `GET /messages/{id}/attachments` | Messages: attach up to 3 files; attachments download with the admin's sign-in |
| `GET /notifications/{id}`, `POST /notifications/{id}/cancel` | Notifications: refresh delivery status; cancel a queued notification |
| `POST /payroll-runs/{id}/mark-paid`, `GET /payroll/audit-events` | Payroll runs: mark a processed run paid; per-run history |
| `POST /fees/send-reminders` | Not wired (D-7) |
| `/api/teacher/*`, `/api/staff/*`, `/api/parent/*` leave and unread routes | Teacher, staff and parent apps, not this admin panel |

## Route coverage (31 Oct 2026)

Every `/school-admin` and `/super-admin` route in the live OpenAPI (639 paths) was compared with what the panel calls.
Connected in this pass: `/dashboard/stats`, `/dashboard/registrations`, `/dashboard/subscriptions`,
`/dashboard/recent-activities`, `/dashboard/recent-schools`, `/subscriptions/expire-due`, `/backups` (+ restore),
`/online-assessments/{id}/questions/from-bank`, `GET /transport-trips/{id}`.

Left unused on purpose:

| Route | Why |
| --- | --- |
| `POST /school-admin/fees/send-reminders` | Sends each student's balance to every parent and student (D-7). |
| `GET /school-admin/people` | Merges teachers and staff without saying which is which, and ids from the two tables can repeat; the panel reads `/teachers` and `/staff`. |
| `GET /school-admin/staff-attendance/today` | The register (`/staff-attendance/register`) already gives today, including staff not yet marked. |
| `GET /school-admin/teachers/{id}/timetable`, `/timetable/daily` | Teacher schedules use `/timetable/weekly`, which has every day. |
| `GET /school-admin/homework-submissions/{id}` | The submissions list already carries every field. |
| `POST /school-admin/transport-trips/{id}/gps` | Sent by the driver's device, not the admin. |
| `GET /super-admin/dashboard/school-status`, `GET /super-admin/backups/{id}` | Same data as `/dashboard` and the backups list. |
| `/super-admin/login`, `/register`, `/me`, `/ping` | The panel signs in through `/auth/*`; registering super admins isn't offered in the UI. |
