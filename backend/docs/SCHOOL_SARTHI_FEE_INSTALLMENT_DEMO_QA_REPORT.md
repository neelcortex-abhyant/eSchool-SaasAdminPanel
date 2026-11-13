# QA report: fee assignment, installments, Request Demo API

Branch `fix/fee-installment-demo` (from `main` 5fdc23f) · 2026-11-13 · not deployed. Live DB checked read-only: `alembic current` = `20261106_0048` (head), so there's nothing to migrate.
Audit (written before any code change): [SCHOOL_SARTHI_FEE_INSTALLMENT_DEMO_AUDIT.md](SCHOOL_SARTHI_FEE_INSTALLMENT_DEMO_AUDIT.md). Integration contract for Vishal: [SCHOOL_SARTHI_FEE_AND_DEMO_API_CONTRACT.md](SCHOOL_SARTHI_FEE_AND_DEMO_API_CONTRACT.md).

Business rules come from the agreed [FEES_TRANSPORT_GRADING_API_CONTRACT.md](FEES_TRANSPORT_GRADING_API_CONTRACT.md) §4–7 plus the existing code. Where the code and that contract disagreed, the contract was followed and the difference is listed below.

## 1. Fee assignment

**Original behaviour:**
- Creating a structure with a `class_id` assigned it to **no one**. A student owed a structure only once an admin assigned them one at a time.
- Duplicates were blocked by a partial unique index, but surfaced as a generic 409.
- Inactive students could be assigned.
- Concession and balance maths existed twice, in float (`/fees/collect`, `/fees/outstanding`) and in Decimal (portal).
- A fixed concession above the total was accepted.
- A concession could make the balance negative.
- Two simultaneous collections could overpay.

**Confirmed rules:**
- A class structure applies to every enrolled student (`admitted` / `active`, not deleted) of that class in that session.
- A student-specific assignment is an **additional** fee, not an override. Reductions are concessions.
- One assignment and one concession per student per structure.
- Payable = total − concession (≥ 0); balance = payable − successful payments.

**Fixes:**
- **Class-level assignment.**
  - Runs automatically when a class structure is created.
  - New idempotent `POST /fee-structures/{id}/assign-class` for later admissions and for existing structures.
  - Only enrolled students, same session, same class (across all its sections), and the branch in scope.
- **Duplicates.**
  - Pre-check, plus the existing DB partial unique index as the guarantee.
  - Clear 409 `"This student already has these fees"`, also for a concurrent insert caught by the index.
  - Class assignment retries once after a race.
- **Validation.** `422 "student is not currently enrolled"` for inactive or transferred students.
- **Concessions.**
  - One Decimal implementation (`school_erp_fees.concession_value` / `assignment_amounts`), used by collect, outstanding and the portal.
  - 422 when an amount is above the total.
  - 422 when the payable would fall below what's already paid.
  - Clear 409 for a second concession.
- **Collect.**
  - Decimal amounts.
  - Assignment row locked (`SELECT … FOR UPDATE`) during the balance check.
  - Exact balance accepted; anything over it refused.
  - Fixed a receipt-number clash (two payments in the same second for one student returned 409).

**Tests:** see §6. Every case listed in the brief is covered, and the concurrent duplicate is tested on SQLite (simulated race) and on PostgreSQL (two real sessions).

## 2. Installments

**Original behaviour:**
- The backend has no generator. The admin app splits the total and sends rows.
- The server already enforced sum == total exactly (Decimal, half-up), and that part was correct.
- Three defects:
  1. **Allocations were shared across students.** Student A paying installment 1 marked it paid for every student on the structure. Student B's payment then went to installment 2, or stayed unallocated.
  2. The "Full payment" label leaked into multi-installment schedules (a frontend `splitInto` bug the server stored as sent).
  3. Changing a structure's amounts without a new schedule silently broke sum == total. Changed amounts also lost their `branch_id`.

**Actual results (persisted rows read back):**

| Case | Total | Saved installments | Sum |
|---|---|---|---|
| Required | 1,200 / 2 | 600.00 + 600.00 (`Installment 1`, `Installment 2`) | 1,200.00 ✔ |
| Single payment | 1,200 / 1 | 1,200.00 (`Full payment`) | ✔ |
| Equal, rounding | 1,000 / 3 | 333.33 + 333.33 + 333.34 | 1,000.00 ✔ |
| Quarterly | 1,000.01 / 4 | 250 × 3 + 250.01 | ✔ |
| Monthly | 1,200 / 12 | 100 × 12 | ✔ |
| Unequal | 1,200 | 200 + 1,000 | ✔ |
| Tiny | 0.03 / 3 | 0.01 × 3 | ✔ |
| Large | 99,999.99 / 3 | 33,333.33 × 3 | ✔ |
| Off by a paisa | 1,200 | 600 + 599.99, or 600 + 600.01 | **422**, nothing saved ✔ |
| Half-paisa inputs | 1,200 | 600.005 + 599.995 → 600.01 + 600.00 | **422** ✔ |

The percentage-based schedule is NOT APPLICABLE: there's no percentage schedule in the API (the frontend computes rupee amounts).

**Label corrections:**
- In a schedule with more than one row, a row named "Full payment" (any case or spacing) is saved as `Installment N` (its position).
- A single-row schedule keeps "Full payment".
- Custom names ("Term 1") are untouched. Existing labels are otherwise preserved, so API compatibility is kept.

**Other fixes:**
- Allocation and per-student installment status now count only that student's payments. A cancelled payment frees its installment.
- Structure responses now include `installments_total` and `installments_match_total`, so a mismatch is visible.
- Amounts are written as Decimal.

**Rounding:** `ROUND_HALF_UP` to 0.01 everywhere. No float in any fee calculation path.

## 3. Request Demo API

- **Existing endpoint found?** No platform Request Demo API. The marketing button links to `/login`.
- **Related existing endpoint:** `POST /api/v1/public/schools/{code}/contact-inquiries`.
  - No auth required; can be called without School Admin login.
  - It's for the website of an **existing** school, which is found by `code`.
  - Contract in the integration doc §6.
  - Hardened here:
    - length limits (name 120, subject 200, message 5000)
    - phone format (7–15 digits)
    - control characters refused
    - its own rate limit (10 per IP per hour; it used to share the forgot-password bucket)
- **Missing:** a platform-level demo request, where a prospect school contacts SchoolSarthi. It wasn't built: the brief says not to create a new API without approval.

**Separate estimate (for approval):**

| Work | Hours |
|---|---|
| `demo_requests` table and Alembic migration (contact_name, school_name, email, phone, city, approx_students, message, status, source, created_at; hashed IP) | 1.5 |
| `POST /api/v1/public/demo-requests`, no auth, strict schema like above, per-IP and per-email limits, honeypot field, `202 {"status":"received"}` with no internal data | 1.5 |
| Super Admin `GET/PATCH /api/v1/super-admin/demo-requests` (list, filter by status, mark contacted or closed) | 2 |
| Notify the sales inbox by email (optional; uses the existing notification delivery) | 1.5 |
| Tests (public access, validation, abuse, Super Admin only) and contract doc | 2 |
| **Total** | **≈ 8.5 h** |

**Note on IPs:** on `main` the rate limit keys on the proxy IP. The real-client fix is on `fix/p0-school-admin-auth-domain` (`TRUSTED_PROXY_HOPS`). Until that branch is merged, the enquiry limit is per proxy, not per visitor.

## 4. Vishal integration status

**Ready (no frontend change needed):**
- `GET/POST/PATCH/DELETE /fee-structures`
- `GET/PUT …/installments`
- `GET/POST/DELETE /fee-assignments`
- `GET/POST/DELETE /fee-concessions`
- `POST /fees/collect`
- `GET /fees/outstanding`
- `GET /fee-payments`, receipts and cancel
- `POST /public/schools/{code}/contact-inquiries`

**Modified contracts (additive, or new error cases):**
- Structure responses gain `installments_total`, `installments_match_total` and, on create, `class_assignment`.
- New 409 and 422 texts for assignments and concessions.
- Stricter public enquiry validation.
- The default receipt number gained a suffix.

**New:** `POST /fee-structures/{id}/assign-class`.

**Pending (need approval):**
- Request Demo API
- School Admin per-student dues route (`GET /students/{id}/fees`); the service already exists for the portal

**Frontend requirements:**
1. Name split rows `Installment N` (`fees.tsx:158`).
2. Send `installments` in the same PATCH as changed `amounts`, and warn when `installments_match_total` is false.
3. Add an "Assign to class" action, and refresh assignments after creating a class structure.
4. Show the server's `detail` text for 409 and 422.
5. Escape enquiry text when rendering it.
6. Don't wire Request Demo until it's approved.

## 5. Final status

| Acceptance criterion | Status | Evidence / reason |
|---|---|---|
| Audit before changes | PASS | Audit doc written first. No edits until it was done. |
| Class-level assignment applies to the class's enrolled students | PASS | Auto on create, plus `assign-class`. SQLite and PG tests. |
| Inactive, transferred, deleted, other session/class/school excluded | PASS | `test_class_structure_assigns_only_enrolled_students_of_that_class` |
| Students admitted later get class fees | PARTIAL | Re-running `assign-class` covers them (tested). Not automatic on admission: students are created in several modules (people, admissions, promotion, transfer), and hooking all of them is outside this brief's "don't change unrelated modules". |
| Student-specific fee is additional, never overwrites class fee | PASS | `test_student_specific_fee_is_additional_and_duplicate_is_409` |
| Assignment request validation | PASS | 6 parametrised invalid cases |
| Fixed and percentage concessions, payable, remaining balance (Decimal) | PASS | Fixed, percent half-up, 100 %, equal-to-total |
| Zero or negative payable handled; excessive concession prevented | PASS | 422 above total, 422 below paid, payable floored at 0, collect refuses on 0 balance |
| Duplicate assignment prevented, including concurrent | PASS | Pre-check, unique index, retry. PG two-session race test. |
| Existing duplicate records handled safely | PASS | The partial unique indexes have existed since migration 0039, so active duplicates can't exist in the DB. No data change needed. |
| ₹1,200 / 2 = 600 + 600, persisted | PASS | SQLite and PG tests read the saved rows |
| Single payment, unequal, rounding, last-installment adjustment, presets | PASS | 10 scenario table above |
| Sum always equals total exactly | PASS | Enforced on save; off-by-a-paisa schedules rejected |
| Correct labels | PASS | Server-side correction. The frontend should still fix its preview (item 1). |
| Percentage-based schedules | NOT APPLICABLE | Not a feature of the API |
| Installment allocation per student | PASS | `test_installment_allocation_is_per_student`, plus the PG test |
| Request Demo API exists | FAIL (by design) | Not present; not built without approval. Estimate in §3. |
| Existing public enquiry: no-auth access, validation, abuse protection | PASS | 18 route tests (missing, invalid, oversized, malformed, extra fields, rate limit) |
| API contract for Vishal | PASS | Contract doc, with examples generated by running the services |
| Targeted tests | PASS | 70 offline plus 2 PostgreSQL |
| Full backend suite | PARTIAL | Still running on the isolated test DB when this was committed (2026-11-13): 7% done, 140 passed, 0 failed, 1 error. Every DB test rebuilds the schema across regions, so the full run takes many hours. The targeted fee tests and the full offline suite above are complete. |
| OpenAPI contract validation | PASS (repo checks) | `test_openapi_*` and `test_erp_openapi_schemas` pass; the new route and fields are in the spec. `openapi-spec-validator` isn't installed, so no external validator was run. |
| Migration status | PASS | `alembic heads` = `20261106_0048` (single head). No migration added; Postgres DDL unchanged. `alembic current` wasn't run against any live DB. |

## 6. Change summary

**Modified:**
- `app/services/v1/school_erp_fees.py`: per-student allocation, `concession_value`, `assignment_amounts`, label rule, Decimal writes
- `app/services/v1/school_academic_mgmt.py`: class assignment, assignment and concession validation, Decimal collect/outstanding with row lock, receipt suffix, structure totals, `branch_id` on PATCHed amounts
- `app/api/v1/school_admin_mgmt.py`: `POST /fee-structures/{id}/assign-class`
- `app/schemas/v1/school_admin_erp_responses.py`: `FeeClassAssignmentOut`; new `FeeStructureOut` fields
- `app/api/v1/school_admin_settings.py`: stricter `PublicContactBody`; its own rate-limit bucket
- `app/core/rate_limit.py`: `CONTACT_PER_IP`
- `app/models/tables.py`: `sqlite_where` on three partial unique indexes so the offline tests match Postgres. No Postgres DDL change.

**Created:**
- `docs/SCHOOL_SARTHI_FEE_INSTALLMENT_DEMO_AUDIT.md`
- `docs/SCHOOL_SARTHI_FEE_AND_DEMO_API_CONTRACT.md`
- this report
- `tests_offline/test_fee_installment_demo.py` (70 tests, in-memory SQLite with the real fee tables)
- `tests/v1/test_fee_installment_pg.py` (2 tests, isolated PostgreSQL `eschool_saas_test`)

**Schema changes / migrations:** none.

**Test results:**
- New offline: **70 passed**. Against the original `main` code the same file gives 31 failed and 18 errors. Some of those are only because the new helpers don't exist there, but the allocation, label, class-assignment, concession and receipt tests fail on the original code for the behaviour itself.
- New PostgreSQL (isolated test DB): **2 passed** in 68 s.
- Offline suite plus fee route, branch-IDOR and ERP route tests: **242 passed**.
- Full suite: Still running on the isolated test DB when this was committed (2026-11-13): 7% done, 140 passed, 0 failed, 1 error. Every DB test rebuilds the schema across regions, so the full run takes many hours. The targeted fee tests and the full offline suite above are complete.

**Remaining limitations:**
- Auto-assignment on later admissions (run `assign-class`).
- Request Demo API and the School Admin per-student dues route need approval.
- A concession isn't spread across installments: per-installment `outstanding` shows face value minus payments, while the assignment balance is correct. Spreading it is a business rule the contract mentions but the code never had; it's left for a decision.
- Structure-level installment `allocated` is a whole-class total.
- The enquiry limit is per proxy IP until the P0 branch merges.
- Existing installment rows already saved with a wrong "Full payment" label aren't rewritten (production data wasn't touched). Read-only query to find them:
  ```sql
  SELECT structure_id, id, name FROM fee_installments i
  WHERE deleted_at IS NULL AND lower(btrim(name)) = 'full payment'
    AND (SELECT count(*) FROM fee_installments j WHERE j.structure_id = i.structure_id AND j.deleted_at IS NULL) > 1;
  ```
