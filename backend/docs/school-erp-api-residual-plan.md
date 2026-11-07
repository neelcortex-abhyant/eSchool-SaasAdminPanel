# School ERP — API Residual Implementation Plan

**Created:** 2026-11-06 (before coding)  
**Mode:** Backend-only. No `admin-web/` edits. No Neon migrate / commit / push / deploy.  
**Source:** API audit + Pre-Implementation Plan (residual fee/report/subdomain gaps).

## Approved scope

Close remaining backend API gaps after secondary branch-isolation closure:

1. **Phase 1 — Fee branch isolation leftovers**  
   Installments GET/PUT, concessions LIST/CREATE/DELETE, payment receipt/PDF/cancel, collection-report.
2. **Phase 2 — Dashboard & reports**  
   `GET /incomes/dashboard` + `/reports/teachers|staff|exams|expenses|income` using existing consolidated branch pattern.
3. **Phase 3 — Subdomain availability**  
   `GET /api/v1/schools/subdomain-availability` per `SCHOOL_DOMAINS_API_CONTRACT.md` §4.
4. **Phase 4 — Offline IDOR/regression tests + docs.**

## Affected routes

| Area | Routes | Dependency |
|---|---|---|
| Installments | `GET/PUT /school-admin/fee-structures/{id}/installments` | `get_branch_context` |
| Concessions | `GET/POST/DELETE /school-admin/fee-concessions[/{id}]` | `get_branch_context` |
| Receipts | `GET …/fee-payments/{id}/receipt[/pdf]`, `POST …/cancel` | `get_branch_context` |
| Collection | `GET /school-admin/fees/collection-report` | `get_branch_context` (or consolidated if matching fees pattern) |
| Dashboard | `GET /school-admin/incomes/dashboard` | `get_branch_context_optional_consolidated` |
| Reports | `/reports/teachers`, `/staff`, `/exams`, `/expenses`, `/income` | `get_branch_context_optional_consolidated` |
| Domains | `GET /api/v1/schools/subdomain-availability` | Public; no school auth |

## Implementation approach

- Reuse `BranchContext` / `get_branch_context` / `get_branch_context_optional_consolidated` from `app/api/v1/deps.py`.
- Derive `school_id` from `AuthContext`; never trust client `school_id` / `branch_id`.
- Services accept `branch_id=` / `allowed_branch_ids=` and enforce ownership with 404 on mismatch (existing convention).
- Stamp `branch_id` on new concessions; filter lists/reports by authorized branch set.
- Parent-child: installments require structure in branch; concessions require student + structure in branch; receipts require payment in branch.
- Subdomain API reuses `school_service` normalize/reserved/domain uniqueness; returns only `{slug, available, problem, suggestions}` — no sensitive school data.
- Classes/subjects catalogs remain school-scoped (inventory A) — unchanged.

## Security requirements

- `X-Branch-Id` is selection hint only.
- Full School Admin consolidated only via `X-Branch-Scope: all` + existing ACL.
- Branch Admin cannot expand beyond assigned branches.
- Preserve payment cancel/idempotency safeguards.
- Do not change path/response contracts unnecessarily.

## Explicitly excluded

- BUG-01 / BUG-02 / BUG-03 (Admin Web)
- Branch switcher / Add Branch UI / fee UX copy
- Neon `0046`/`0047` apply
- SMTP/FCM live delivery, payment gateway, original 29 pack, live §11 E2E

## Success criteria

- Phases 1–3 coded; offline suites green; docs updated; no live-DB claims.
- BUG-01–03 remain FE-blocked; Neon still unapplied.

## Status

- Plan artifact: **written** (before coding)
- Implementation: **COMPLETE offline** (2026-11-06)
- Combined offline suites: **194 passed, 0 failed, 2 warnings**
- Neon / live DB: **not verified**
- BUG-01–03 / Admin Web: **still blocked (out of scope)**
