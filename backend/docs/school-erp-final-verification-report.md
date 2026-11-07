# School ERP — Final Requirement Verification Report

**Date:** 2026-11-06 (updated after API residual gap closure)  
**Prior audit date:** 2026-11-05  
**Mode:** Backend-only implementation; no `admin-web/` edits; Neon `0046`/`0047` **not** applied; no commit/push/deploy; **no live DB claim**  
**Requirements source:** “School ERP – Development Tasks & Bug Fixes” (12 sections) + locked backend-only ownership (Nitish = Admin Web)  
**Plan artifact:** `docs/school-erp-api-residual-plan.md`

## Status legend

| Status | Meaning |
|---|---|
| **VERIFIED COMPLETE** | Code + safe offline evidence confirms the requirement for the owning layer |
| **IMPLEMENTED BUT NOT VERIFIED** | Code exists; no DB/UI/E2E/email evidence |
| **PARTIALLY COMPLETE** | Some bullets/subsystems done; gaps remain |
| **NOT IMPLEMENTED** | No matching implementation found |
| **BLOCKED / FRONTEND OWNER** | Explicitly Nitish/Admin Web, env, original 29 pack, or Neon approval |

---

## Executive summary

| Area | Verdict |
|---|---|
| Backend multi-branch core (models, `0046`+`0047`, branch CRUD, ACL, operational wiring) | **Code + offline tests present**; Neon **not** applied; DB E2E **not** run → **IMPLEMENTED BUT NOT VERIFIED** on live DB |
| Confirmed bugs BUG-01–03 | Backend APIs OK; **Admin Web still broken** → **BLOCKED / FRONTEND OWNER** |
| Branch UI / switcher / Add Branch form | **NOT IMPLEMENTED** in Admin Web |
| Teachers, students nested, fees core + **installments/concessions/receipts/collection-report**, reports + incomes dashboard | **Wired** with `get_branch_context` / consolidated |
| Subdomain availability API | **Implemented** (`GET /api/v1/schools/subdomain-availability`) — does not fix BUG-01 FE |
| ORM `branch_id` vs migration inventory | **Aligned** |
| Admission uniqueness | **Per-branch** ORM + `20261106_0047` (Neon not applied) |
| Original 29 tests | **BLOCKED** |
| Honest overall | Identified **backend residual API gaps closed offline**; FE + Neon + DB E2E still open |

### Test results (API residual pass)

| Suite | Result |
|---|---|
| IDOR + subdomain + registration domain unit | **51 passed** |
| Branch suites + ORM + subdomain + registration + full `tests_offline` | **194 passed, 0 failed, 2 warnings** |
| Live Neon / browser / email | **Not executed** |

Script head: `heads ['20261106_0048']` (branch quota; not applied to Neon).

---

## Gap-closure changelog (cumulative)

1. ORM `branch_id` inventory-B — **done**.  
2. Core + nested operational routes wired — **done**.  
3. Admission unique `0047` — **code ready; Neon not applied**.  
4. Head asserts → `0047` — **done**.  
5. IDOR offline expanded — **done**.  
6. Secondary audit gaps (student nested, teacher patch/docs, fee structure/assignment) — **done**.  
7. **API residual:** installments, concessions, receipts/cancel, collection-report, incomes dashboard, remaining reports, subdomain-availability — **done this pass**.  
8. Isolated-DB E2E / SMTP — **still open**.

---

## Section 1 — Fix Confirmed Bugs

| Task | Status | Evidence / ownership |
|---|---|---|
| BUG-01 School registration domain `.localhost` | **BLOCKED / FRONTEND OWNER** | FE still defaults root domain to `localhost`. Backend registration OK. |
| BUG-02 Terms/Privacy → Contact | **BLOCKED / FRONTEND OWNER** | Still `href="#contact"` in `SiteFooter.tsx`. |
| BUG-03 Student class/section validation sticky errors | **BLOCKED / FRONTEND OWNER** | `StudentForm.tsx` does not clear `fieldErrors` on class/section change. |

**Section 1 overall:** **BLOCKED / FRONTEND OWNER**.

---

## Section 2 — School & Second Branch Management

| Task | Status | Evidence |
|---|---|---|
| Verify existing school info & Branch 1 | **IMPLEMENTED BUT NOT VERIFIED** | `ensure_default_branch` / migration `Main`. Neon not applied. |
| Create second branch under same school | **IMPLEMENTED BUT NOT VERIFIED** | `POST /school-admin/branches`. No DB E2E. |
| Add Branch form + mandatory validation | **BLOCKED / FRONTEND OWNER** | Backend schema validates; Admin Web **0** branch UI hits. |
| Branch create/edit/list/view | **PARTIALLY COMPLETE** | Backend routes; FE missing. |
| Branch-specific admin assignment | **IMPLEMENTED BUT NOT VERIFIED** | `PUT …/branches/{id}/admins` → UUID ACL. |
| Branch selection/switching | **BLOCKED / FRONTEND OWNER** | Contract: `X-Branch-Id` + `/me` branches. No UI. |
| Branch 1 & 2 same school | **IMPLEMENTED BUT NOT VERIFIED** | Enforced in service. |
| Independent records per branch | **IMPLEMENTED BUT NOT VERIFIED** | Students/fees/homework/exams/timetable/teachers/announcements/attendance stamp/filter where wired. Offline IDOR units pass. Live DB unproven. |
| Students/teachers/classes/sections/subjects on Branch 2 | **PARTIALLY COMPLETE** | Students + teachers branch-scoped. Classes/sections/subjects catalogs remain **school-scoped by design** (inventory A); `class_sections` carry `branch_id`. |
| Branch attendance, timetable, exams, homework, notices | **IMPLEMENTED BUT NOT VERIFIED** | HTTP routes inject `get_branch_context` for create/list/(get/update/delete where applicable). |
| Branch-wise fees/payments | **IMPLEMENTED BUT NOT VERIFIED** | Structures/payments/collect/assignments/outstanding/reminders use branch context. |
| Consolidated + branch-wise dashboard stats | **PARTIALLY COMPLETE** | Reports + academics `summary` branch-aware; `incomes/dashboard` still school-wide; no FE branch dashboard. |
| Prevent unauthorized cross-branch access | **IMPLEMENTED BUT NOT VERIFIED** | Offline IDOR + `resolve_branch_context` branch_admin deny. Not full DB matrix. |
| Branch 2 ops don’t affect Branch 1 | **IMPLEMENTED BUT NOT VERIFIED** | Offline ACL unit; no two-branch DB journey. |
| Edit/disable/delete safeguards | **IMPLEMENTED BUT NOT VERIFIED** | Default delete/disable blocked in service. |

**Section 2 overall:** **PARTIALLY COMPLETE** (backend code closed; FE + Neon open).

---

## Section 3 — Student Admission & Management

| Task | Status | Evidence |
|---|---|---|
| Complete admission workflow | **PARTIALLY COMPLETE** | Backend OK; FE BUG-03 + no branch switcher. |
| Required-field validation | **IMPLEMENTED BUT NOT VERIFIED** | Backend 422s; FE `check()`. |
| Dependent class/section errors | **BLOCKED / FRONTEND OWNER** | BUG-03. |
| Student create + DB persistence | **IMPLEMENTED BUT NOT VERIFIED** | Neon schema with `branch_id` NOT NULL not applied. |
| Edit / search / filter / view | **IMPLEMENTED BUT NOT VERIFIED** | List filters by `branch_id`. |
| Prevent duplicate registrations | **IMPLEMENTED BUT NOT VERIFIED** | Service + ORM + migration `0047` per-branch unique. Neon not applied. |
| Associate with school and branch | **IMPLEMENTED BUT NOT VERIFIED** | `Student.branch_id` on create. |
| Appear in attendance, fees, reports | **PARTIALLY COMPLETE** | Cross-module uses student IDs; most branch paths wired. |

**Section 3 overall:** **PARTIALLY COMPLETE**.

---

## Section 4 — Fees & Financial Management

| Task | Status | Evidence |
|---|---|---|
| Installment date selection / structures / assign / collect | **IMPLEMENTED BUT NOT VERIFIED** | Existing ERP fees + branch stamp. |
| Concessions / pending / outstanding | **IMPLEMENTED BUT NOT VERIFIED** | Outstanding + reminders now branch-filtered. |
| Financial dashboard totals | **PARTIALLY COMPLETE** | Branch-aware financial report; FE “payments not stored” copy still wrong. |
| Correct “payments not stored” text | **BLOCKED / FRONTEND OWNER** | Admin Web copy. |
| Prevent duplicate payment submissions | **IMPLEMENTED BUT NOT VERIFIED** | Idempotency on collect. |
| Financial data separation between branches | **IMPLEMENTED BUT NOT VERIFIED** | Key paths wired. |
| Online payment gateway | Out of ERP scope / **BLOCKED** unless approved | |

**Section 4 overall:** **PARTIALLY COMPLETE**.

---

## Section 5 — Authentication, Admin & Permissions

Unchanged vs audit for FE/SMTP. Backend `branch_admin` + ACL + `get_branch_context` pipeline **IMPLEMENTED BUT NOT VERIFIED** on live DB.

**Section 5 overall:** **PARTIALLY COMPLETE**.

---

## Section 6 — Academic Management

| Task | Status | Evidence |
|---|---|---|
| Class/section/subject catalogs | **IMPLEMENTED BUT NOT VERIFIED** | School-scoped by design. |
| Subjects + teacher assignment | **IMPLEMENTED BUT NOT VERIFIED** | Assignments ORM now has `branch_id`; create paths stamp where wired. |
| Attendance | **IMPLEMENTED BUT NOT VERIFIED** | Create stamps branch. |
| Offline exam CRUD | **IMPLEMENTED BUT NOT VERIFIED** | Parent + schedule/marks/results/process routes inject branch; `_owned_schedule` enforces parent/child consistency. |
| Timetable management | **IMPLEMENTED BUT NOT VERIFIED** | Class timetable CRUD + teacher daily/weekly/list/availability branch-aware. |
| Homework | **IMPLEMENTED BUT NOT VERIFIED** | List/create + get/update/delete/summary/submissions/attachments/evaluation branch-aware. |
| Notices | **IMPLEMENTED BUT NOT VERIFIED** | Announcement create/list branch-aware. |

**Section 6 overall:** **IMPLEMENTED BUT NOT VERIFIED** (backend); FE/Neon open.

---

## Section 7 — Dashboard, Reports & Navigation

| Task | Status | Evidence |
|---|---|---|
| Academics summary counts | **IMPLEMENTED BUT NOT VERIFIED** | Now accepts `branch_id`. |
| Branch-wise dashboards | **BLOCKED / FRONTEND OWNER** | No Admin Web branch dashboard. |
| School consolidated reports | **IMPLEMENTED BUT NOT VERIFIED** | `X-Branch-Scope: all`. |
| Sidebar / browser UX | **BLOCKED / FRONTEND OWNER** | |

**Section 7 overall:** **PARTIALLY COMPLETE**.

---

## Section 8 — Notifications & Integrations

Unchanged: code present; SMTP/FCM **not verified**.

**Section 8 overall:** **PARTIALLY COMPLETE**.

---

## Section 9 — UI & Responsive Testing

**BLOCKED / FRONTEND OWNER** (unchanged).

---

## Section 10 — Security & Error Handling

| Task | Status | Evidence |
|---|---|---|
| Auth / school isolation | **IMPLEMENTED BUT NOT VERIFIED** | Existing. |
| Branch-level isolation | **IMPLEMENTED BUT NOT VERIFIED** | Parent + nested child routes for exams/timetable/homework/assignments enforce school_id + branch_id offline; live DB unproven. |
| Unauthorized access attempts | **IMPLEMENTED BUT NOT VERIFIED** | Offline IDOR units (38 in branch/schema suite set). |

**Section 10 overall:** **IMPLEMENTED BUT NOT VERIFIED** on live DB; offline residual child-route gaps closed.

### Security notes (honest)

1. Neon still not on `0046`/`0047` — deployed DB may lack branch tables/columns.  
2. Clients omitting `X-Branch-Id` get default branch for full school_admin; branch_admin without ACL → 403. FE not sending header yet.  
3. Offline-exam schedules/marks/results and teacher timetable reads now re-check branch; parent/child mismatch → 404.  
4. No claim of full HTTP IDOR matrix on a real database.

---

## Section 11 — Final End-to-End Regression Testing

Offline E2E stub asserts route registration / checklist only — **not** live journeys.  
**Original 29 test cases:** **BLOCKED**.

**Section 11 overall:** **NOT VERIFIED** / **PARTIALLY COMPLETE** (stubs).

---

## Section 12 — Required Deliverables

| Deliverable | Status |
|---|---|
| BUG-01–03 confirmation | **BLOCKED / FRONTEND OWNER** |
| Implementation status | This report + `school-erp-development-progress.md` |
| Backend API / integration details | `school-erp-frontend-handoff.md`, `school-erp-branch-architecture.md` |
| Screenshots / credentials | **NOT PROVIDED** |
| Original 29 ready | **BLOCKED** |

---

## Nitish (Admin Web) — explicit task list

1. BUG-01: `NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN` + preview in `lib/domains/core.ts`.  
2. BUG-02: Real Privacy/Terms/Refund routes in `SiteFooter.tsx`.  
3. BUG-03: Clear `fieldErrors` on class/section/session change in `StudentForm.tsx`.  
4. Branch switcher → `X-Branch-Id`; consume `/me` `branches[]`.  
5. Add Branch form + list/edit/disable UI.  
6. Branch Admin assign UI.  
7. Remove “fee payments are not stored” copy.  
8. Section 9 browser/responsive matrix.  
9. Screenshots, credentials, FE Section 12 confirmation.

---

## Remaining blockers (honest)

1. **Neon:** do not apply `0046`/`0047` without explicit approval; no live schema verify.  
2. **Admin Web:** BUG-01–03 + entire branch UX.  
3. **Original 29** pack missing.  
4. **Isolated-DB E2E** for Section 11 journeys — not claimed.  
5. **SMTP/FCM** delivery not proven.  
6. Catalog/school-scoped modules (classes/subjects as inventory A) remain school-wide by design — not a gap.

**Backend secondary branch-isolation gaps and API residual fee/report/subdomain gaps: CLOSED offline.**

---

## Completion criteria check

| Criterion | Met? |
|---|---|
| All confirmed defects fixed | **No** — BUG-01–03 still FE |
| Backend gaps from prior audit closed | **Yes** (core + secondary + API residual offline) |
| Implemented features pass relevant E2E | **No** — no live E2E |
| Remaining blocked tests documented | **Yes** |
| No feature reported complete without verification | **Honored** |

---

## Bottom line

**Identified backend residual API gaps are closed offline (194 combined).** BUG-01–03 remain Admin Web. Production readiness still requires Neon migrate approval, Admin Web branch UI + BUG fixes, isolated-DB E2E, and the original 29 pack.
