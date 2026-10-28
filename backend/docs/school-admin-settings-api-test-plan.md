# School Admin Settings / CMS / Support — Test Plan

**Companion docs:** [school-admin-settings-api-audit.md](./school-admin-settings-api-audit.md), [school-admin-settings-api-plan.md](./school-admin-settings-api-plan.md)  
**Rule:** Run tests only against an **isolated** test database (`TEST_DATABASE_URL` / `eschool_saas_test`). Never against live Neon `eschool_saas_v1`. Do not weaken [`tests/conftest.py`](../tests/conftest.py) / [`pg_test_utils.py`](../tests/pg_test_utils.py) guards.

---

## 1. Environment

| Item | Requirement |
|------|-------------|
| DB | Dedicated Postgres test DB derived per project rules |
| Env | `APP_ENV=test`, `ALLOW_DDL` only as existing tests allow |
| Secrets | Fake Fernet/app keys in test settings; never production keys |
| Alembic | Apply migrations on **test** DB only when implementing; not part of this docs-only delivery |

**DB-free checks (always runnable):** OpenAPI path registration; Alembic revision chain; Pydantic schema validation; secret-masking unit tests without DB.

---

## 2. Cross-cutting cases (every new school-admin settings endpoint)

| Case | Expect |
|------|--------|
| No `Authorization` | 401 |
| Non–school-admin token | 403 |
| School Admin without `settings.manage` (if role matrix excludes it) | 403 |
| Cross-school resource id | 404 or 403 (match existing school-admin convention) |
| Extra body fields | 422 (`extra=forbid` where used) |
| Soft-deleted row | 404 on get/update |
| Success | 200/201 with school-owned payload only |
| Audit (sensitive writes) | Audit row without secret plaintext |

---

## 3. Phase A — Content pages + FAQs

| Test | Detail |
|------|--------|
| PUT content slug allowlist | Valid slugs succeed; unknown slug 422 |
| GET after PUT | Body/title round-trip for school A |
| Isolation | School B cannot read/update school A page |
| FAQ CRUD | Create/list/patch/soft-delete; pagination |
| Regression | Existing sliders/gallery routes still registered and pass prior tests |

**Suggested file:** `tests/v1/test_school_admin_content_cms.py`

---

## 4. Phase B — Leave settings + online exam terms

| Test | Detail |
|------|--------|
| GET default | Empty or server defaults without inventing business rules |
| PUT then GET | Idempotent round-trip of approved schema fields |
| Isolation | Per-school rows |
| Stub note | Document that legacy `GET /api/leave-settings` may still be 501 until deprecated |

**Suggested file:** `tests/v1/test_school_admin_leave_and_exam_terms.py`

---

## 5. Phase C — Email templates

| Test | Detail |
|------|--------|
| Unique key per school | Duplicate active key → 409 |
| CRUD | Create/list/get/patch/delete |
| Isolation | Cross-school 404 |
| No send required | First wave does not require SMTP |

**Suggested file:** `tests/v1/test_school_admin_email_templates.py`

---

## 6. Phase D — Secrets (WhatsApp, payment gateway, third-party)

| Test | Detail |
|------|--------|
| PUT with secret | 200; GET returns `configured: true`, value `null` |
| GET never echoes secret | Assert response JSON has no token/password substrings for secret fields |
| Update secret | Re-configure clears old ciphertext |
| Clear secret | `configured: false` |
| Logs/audit | Metadata keys redacted ([`audit_service.sanitize_metadata`](../app/services/v1/audit_service.py)) |
| SaaS payments regression | `/api/v1/payments*` and platform settings still work; school gateway settings do not overwrite env Razorpay |

**DB-free unit:** encrypt/decrypt helper round-trip; mask helper.

**Suggested file:** `tests/v1/test_school_admin_integration_secrets.py`

---

## 7. Phase E — User form fields

| Test | Detail |
|------|--------|
| CRUD definitions | entity type allowlist (`student|staff|parent|…`) |
| Invalid type | 422 |
| Isolation | Per school |
| No invent | Do not assert people create requires custom fields until that follow-up lands |

**Suggested file:** `tests/v1/test_school_admin_form_fields.py`

---

## 8. Phase F — Contact inquiries + support tickets

| Test | Detail |
|------|--------|
| Distinct from admission | Creating contact inquiry does not create `AdmissionInquiry` |
| School inbox list/filter | status filter, pagination |
| Ticket + message thread | Create ticket, add message, list messages |
| Isolation | Cross-school ticket id 404 |
| Optional public POST | Rate limit / 422 validation; no auth; cannot set school_id arbitrarily (resolve via school code) |

**Suggested files:** `tests/v1/test_school_admin_contact_inquiries.py`, `tests/v1/test_school_admin_support_tickets.py`

**Also:** Add/expand tests for existing `/admission-inquiries` (audit: **Existing needs testing**).

---

## 9. Phase G — Super Admin backup / restore

| Test | Detail |
|------|--------|
| School Admin token | 403 on all backup routes |
| Super Admin create | Job metadata 201/200; no dump bytes in list response |
| Restore without confirmation | 422 |
| Restore with flag off | 403/503 in production-like settings |
| Audit | create/restore attempts logged |
| Retention | Expired backup not restorable |

**Suggested file:** `tests/v1/test_super_admin_backups.py`  
**Caution:** Prefer mocking storage I/O; never point restore at shared live DB in CI.

---

## 10. Regression suite (after each phase)

| Suite | Why |
|-------|-----|
| `tests/v1/test_phase8_platform.py` | Platform settings |
| Payment tests under `tests/v1/` | SaaS billing |
| School admin people / offline exams smoke | No accidental router break |
| `tests_offline/` parity if new Alembic head | Head revision assertions |

---

## 11. OpenAPI / registration checks (DB-free)

After routes land:

```text
Assert paths exist for:
  /api/v1/school-admin/content/{slug}
  /api/v1/school-admin/faqs
  /api/v1/school-admin/leave-settings
  /api/v1/school-admin/online-exam-terms
  /api/v1/school-admin/email-templates
  /api/v1/school-admin/whatsapp-settings
  /api/v1/school-admin/payment-gateway-settings
  /api/v1/school-admin/contact-inquiries
  /api/v1/school-admin/support-tickets
  /api/v1/super-admin/backups
```

Pattern: same style as `tests/v1/test_school_admin_schedule_patch.py` / `tests_offline/`.

---

## 12. Explicit non-goals for this docs delivery

- No pytest execution against production  
- No `alembic upgrade` on Neon  
- No application code changes  
- No inventing leave/payment business-rule assertions beyond schema round-trip
