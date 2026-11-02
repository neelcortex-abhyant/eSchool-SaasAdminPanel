# Note for Nitish: final backend spec vs. what's live (1 Nov 2026)

From Vishal's side, read-only. I checked against the live OpenAPI on Render (639 paths) and `origin/main` at `42eaaee`.
Routes below are under `/api/v1/school-admin` unless shown. The spec's proposed paths (`/api/v1/school/...`)
differ from ours; **please keep the current `/school-admin/...` paths**, since the admin panel already calls them.

## 1. Spec vs. backend

| Spec item | State | Today |
| --- | --- | --- |
| Template CRUD | Partial | `GET/POST /certificate-templates`, `PATCH/DELETE /{id}`. Missing: **activate/deactivate** (no status field); a fixed list of **types** (Bonafide, Transfer, Character, Achievement, Experience; `template_type` is free text, default "general"); **placeholder validation**; **branding fields** (logo, signature, school name/address). |
| Generate certificate | Partial | `POST /certificates/issue` (student), `/certificates/issue-staff`. School ownership is checked (`_owned`, `_same_school`). The number is unique, and there's a verify token plus a QR URL. |
| Certificate PDF | **Defect** | `GET /certificates/{id}/pdf` prints `template.body_text` **raw**: placeholders like `{student_name}` aren't filled from the student/staff record or `data_json`. There's no logo, school name/address or signature. |
| History, re-download, revoke, verify | Exists | `GET /certificates?student_id&staff_id&status`, `GET /{id}`, `/{id}/pdf`, `POST /{id}/revoke`, `GET /public/certificates/verify/{token}` |
| Student ID card | Partial | `GET /students/{id}/id-card` returns JSON (ids only for class, section and session; `image`, `qr_code_url`). There's **no PDF/printable file** and **no bulk route**; the panel renders cards and loops for bulk. |
| Staff ID card | Partial | `GET /staff/{id}/id-card` returns JSON (`employee_id`, department, designation, `qr_code_url`). Same gaps: no PDF, no bulk. |
| Student reports | Partial | `/reports/students` has the total and status only. Missing: session/class/section counts, admission trends, attendance summaries, monthly attendance %. There are **no filters**. |
| Academic reports | Partial | `/reports/exams` has counts only; `/offline-exams/{id}/results` and `/summary` are per exam. Missing: class/subject analysis, grade distribution, trends. |
| Financial reports | Mostly exists | `/fees/collection-report?from_date&to_date&class_id` (`by_method`, items), `/fees/outstanding` (summary), `/reports/financial-summary`, income and expenses. Missing: overdue totals, monthly trend, class-wise summary. |
| Staff and payroll reports | Partial | `/reports/staff`, `/reports/teachers`, `/staff-attendance/reports` (with `by_month`), `/leave-balances`, `/payroll/summary?year`. Missing: leave statistics and department-wise payroll. |
| Transport reports | Partial | `/transport/reports/trips` (paged). Missing: route-wise allocation and utilisation (the panel counts these from `/student-transport-assignments`). |
| Super-admin analytics | Exists | `/super-admin/dashboard` (+ `/stats`, `/registrations?year`, `/subscriptions`, `/recent-activities`, `/recent-schools`, `/school-status`) and `/super-admin/reports/schools`, `/subscriptions`, `/bills` (`amount_sum`). Missing: a monthly revenue summary. |
| Report infrastructure | Missing | No date/session/class filters on most report routes, no CSV/PDF export routes. The panel exports CSV and prints in the browser today. |
| Security, tenant isolation, production | Not started | No cross-tenant tests found in `tests_offline`; see the known issues below. |

## 2. Contract the admin panel relies on (please don't break)

- **Certificates:**
  - `certificate-templates` items have `id, name, template_type, body_text`.
  - `issue` takes `{template_id, student_id, certificate_no?, data}`; `issue-staff` takes `{template_id, staff_id, certificate_no?, data}`.
  - Responses must include `id, certificate_no, status, verify_url, qr_verify_url, issued_at`.
  - `GET /certificates?status=` is used for the list; `/{id}/pdf` must return `application/pdf` with a Bearer token; `/{id}/revoke`.
- **ID cards:**
  - `students/{id}/id-card` fields: `admission_no, roll_number, class_section_id, session_year_id, first_name, last_name, image, qr_code_url, qr_verify_url, settings`.
  - The staff card: `employee_id, department, designation, …`.
  - `GET/PUT /id-card-settings {front_template, back_template, show_fields}`.
  - If you add PDF or bulk routes, please add them **next to** these JSON routes, not instead of them.
- **Reports page** (`/school/reports`) calls:
  - `/reports/students`, `/reports/staff`, `/reports/financial-summary`
  - `/fees/collection-report`, `/fees/outstanding`
  - `/staff-attendance/reports?from_date&to_date`, `/payroll/summary?year`
  - `/offline-exams` + `/{id}/results`, `/academics/attendances`, `/students`, `/staff`, `/teachers`, `/academics/leaves`, `/leave-types`
  - `/transport-routes`, `/vehicles`, `/transport-trips` (+ `/{id}/attendance`)

  New aggregate routes are welcome; please keep these shapes, and send me the new contract so I can switch over.
- **Lists:** `{items, total, page, page_size}`, max `page_size` 50. Errors: `{detail}` (string or a FastAPI list).

## 3. Known issues found so far

| # | Issue | Priority |
| --- | --- | --- |
| 1 | **Notifications go to whole roles.** `POST /fees/send-reminders` sends "balance for student #N" to every parent and student. Student-absence notices go to all parents, and leave decisions to all staff and teachers. Target the specific family or person. Nothing sends until Firebase credentials are set. | P0 before enabling FCM |
| 2 | **Migrations 0044/0045**: your report says they weren't applied on Neon, while the code using them is live (leave decisions, notification retry/idempotency, attachments, payroll). Please confirm or apply them. | P0 |
| 3 | **Backups only write a record** (`metadata_only`; "full pg_dump not wired"), and restore only records the request. There's no documented recovery procedure. | P1 |
| 4 | **School logos** are stored on the Next.js server's disk (`/api/school-logos`), which Netlify doesn't keep. A backend upload/serve route is needed. | P1 |
| 5 | **Custom domains**: `GET/PATCH /school-admin/domain` and `POST /domain/verify` don't exist (see `SCHOOL_DOMAINS_API_CONTRACT.md`). | P2 |
| 6 | **Attendance**: the generic PATCH refuses `attendances`; there's no lock/unlock, no Leave status, and no date/class filters on `/academics/attendances` (the panel reads every page). | P1 |
| 7 | **No PATCH** for `/transport-stops/{id}`, `/student-transport-assignments/{id}`, `/fee-concessions/{id}` (admins must delete and re-add). | P2 |
| 8 | **Student `user_id`**: it's in `StudentOut` now. Please keep it in list items too; leave and messaging rely on it. | P2 |
| 9 | **`admin-web` was deleted on `main`** twice (`b1258e9`, `ce89003`). Netlify builds from `admin-web`, so please pull before pushing, and don't delete it. | P0 process |
| 10 | Leave PATCH now refuses status changes (good). The panel uses `/leaves/{id}/approve|reject|cancel`; that fix is ready but not yet pushed by Vishal. | — |
