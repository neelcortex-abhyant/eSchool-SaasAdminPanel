# School ERP Development Progress

Last updated: 2026-11-06 (API residual gap closure)

| Task ID | Status | Notes |
|---|---|---|
| Phase 0–9 | COMPLETE | Multi-branch core + nested security |
| Secondary route branch gaps | COMPLETE | Student nested, teacher patch/docs, fee structure/assignment |
| API residual (fees leftovers + reports + subdomain) | COMPLETE | Offline green |
| Phase 10 E2E | PARTIAL | Offline stubs only |
| Original 29 tests | BLOCKED | Not in repository |
| Neon `0046`/`0047` | BLOCKED | Not applied (policy) |
| BUG-01–03 | BLOCKED | Frontend owner (Nitish) |

## API residual gap closure (2026-11-06)

Plan artifact: `docs/school-erp-api-residual-plan.md` (written before coding).

### Phase 1 — Fee branch isolation
- Installments GET/PUT → `get_branch_context` + structure `branch_id`
- Concessions LIST/CREATE/DELETE → stamp/filter `branch_id`; parent student+structure checks
- Receipt / PDF / cancel → payment `branch_id`
- Collection report → filter `FeePayment.branch_id`

### Phase 2 — Reports / dashboard
- `GET /incomes/dashboard` + teachers/staff/exams/expenses/income reports → `get_branch_context_optional_consolidated`
- Classes/subjects remain school-scoped by design

### Phase 3 — Subdomain availability
- `GET /api/v1/schools/subdomain-availability` per contract §4
- Does **not** fix BUG-01 FE `.localhost` preview

### Test evidence

| Suite | Result |
|---|---|
| IDOR + subdomain + registration domain unit | **51 passed** |
| Branch suites + ORM parity + subdomain + registration + `tests_offline` | **194 passed, 0 failed, 2 warnings** |

```text
python -m pytest --noconftest -p no:cacheprovider tests/v1/test_school_branches_offline.py tests/v1/test_school_branch_idor_offline.py tests/v1/test_school_erp_e2e_offline.py tests/v1/test_modules_orm_migration_parity.py tests/v1/test_subdomain_availability_offline.py tests/v1/test_school_registration_domain_unit.py tests_offline -q --tb=line
```

No Neon migrate. No live DB verification claimed.

## Files touched this pass

- `docs/school-erp-api-residual-plan.md` (new)
- `app/api/v1/school_admin_erp.py`
- `app/api/v1/school_admin_mgmt.py`
- `app/api/v1/school_registration.py`
- `app/services/v1/school_erp_fees.py`
- `app/services/v1/school_academic_mgmt.py`
- `app/services/v1/school_service.py`
- `app/schemas/v1/school_registration.py`
- `tests/v1/test_school_branch_idor_offline.py`
- `tests/v1/test_subdomain_availability_offline.py` (new)
- `docs/school-erp-development-progress.md`
- `docs/school-erp-final-verification-report.md`

## Still blocked

Neon migrate, Admin Web (BUG-01–03 + branch UI), original 29, isolated-DB E2E, SMTP/FCM delivery.
