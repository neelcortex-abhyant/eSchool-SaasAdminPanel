# School Admin Settings / CMS / Support — API Audit

**Date:** 2026-10-28  
**Source checklist:** Handwritten School Admin feature list (System Setting, Web Setting, Database backup, Contact Inquiry, Support)  
**Scope:** Read-only verification against the FastAPI backend. No application code was changed for this document.

**Classification key**

| Label | Meaning |
|-------|---------|
| Fully implemented | Real routes + models/services; suitable for production use pending regression |
| Partially implemented | Some related surface exists; CMS/admin write or school scope incomplete |
| Missing | No usable school-admin (or required) API |
| Existing needs testing | Code exists; focused tests missing or thin |

**Scope defaults (product plan)**

- School-scoped CMS and secrets under `/api/v1/school-admin/...` with `settings.manage` where appropriate.
- Platform SaaS Razorpay + [`settings_service.py`](../app/services/v1/settings_service.py) remain Super Admin / env.
- Full Neon database backup/restore is **Super Admin only** (shared tenancy).

---

## 1. System Settings

### 1.1 Leave settings

| Field | Value |
|-------|--------|
| **Status** | **Missing** |
| **Verified** | Stub only: `GET /api/leave-settings` → HTTP 501 `contract-stub` in [`app/api/stubs.py`](../app/api/stubs.py) (approx. line 67). |
| **Do not confuse with** | Leave **requests**: model `Leave` in [`app/models/tables.py`](../app/models/tables.py); school-admin academics resource `leaves` via [`app/api/v1/school_admin_academics.py`](../app/api/v1/school_admin_academics.py) (`RESOURCE_PERMISSIONS` / teachers.manage). Also legacy `/api/admin/leaves`. |
| **Assumption** | None for “missing settings CMS.” Leave request CRUD is verified separately. |

### 1.2 Additional user fields

| Field | Value |
|-------|--------|
| **Status** | **Missing** |
| **Verified** | Laravel catalog names only: `form_fields`, `extra_student_datas` in [`app/models/catalog.py`](../app/models/catalog.py). No ORM models, Alembic tables, or school-admin routes for custom form fields. |
| **Related (not the same)** | Fixed profile columns on `v1_users` (e.g. Alembic `20261014_0011`) and people APIs under `/api/v1/school-admin/students|teachers|staff`. |

### 1.3 WhatsApp configuration / Meta WhatsApp credentials

| Field | Value |
|-------|--------|
| **Status** | **Missing** |
| **Verified** | `GET/POST /api/whatsapp/webhook/{schoolCode}` → 501 in [`app/api/stubs.py`](../app/api/stubs.py). No WhatsApp models, env keys for Meta tokens, services, or migrations. |

### 1.4 Online exam terms

| Field | Value |
|-------|--------|
| **Status** | **Missing** (as school-wide CMS) |
| **Verified** | Per-assessment text only: `OnlineAssessment.instructions` in [`app/models/tables.py`](../app/models/tables.py) + online assessment APIs in [`app/api/v1/school_admin.py`](../app/api/v1/school_admin.py) / [`school_online_assessments.py`](../app/services/v1/school_online_assessments.py). No school-level “online exam terms & conditions” resource. |

### 1.5 Email templates

| Field | Value |
|-------|--------|
| **Status** | **Missing** |
| **Verified** | [`app/services/v1/mailer.py`](../app/services/v1/mailer.py) sends plain-text SMTP using env (`smtp_*` in [`app/core/config.py`](../app/core/config.py)). Platform secret `smtp_password` via [`settings_service.py`](../app/services/v1/settings_service.py). No EmailTemplate model/API. |

### 1.6 Payment settings

| Field | Value |
|-------|--------|
| **Status** | **Partially implemented** |
| **Verified (platform SaaS)** | Razorpay via env + `/api/v1/payments*` ([`app/api/v1/payments.py`](../app/api/v1/payments.py)); school billing list under [`school_payments.py`](../app/api/v1/school_payments.py). Platform key `payment_secret_key` in `SECRET_SETTING_KEYS` ([`settings_service.py`](../app/services/v1/settings_service.py)). |
| **Missing (school fee gateway CMS)** | Catalog name `payment_configurations` unmapped ([`catalog.py`](../app/models/catalog.py)). No school-admin CRUD for fee collection gateway credentials. |

### 1.7 Third-party API configuration

| Field | Value |
|-------|--------|
| **Status** | **Partially implemented** |
| **Verified** | Platform-only secret keys: `smtp_password`, `payment_secret_key`, `firebase_private_key`, `webhook_secret` in [`settings_service.py`](../app/services/v1/settings_service.py); CRUD at `GET/PATCH /api/v1/super-admin/settings` ([`app/api/v1/super_admin/settings.py`](../app/api/v1/super_admin/settings.py)). |
| **Missing** | School-scoped third-party integration registry (WhatsApp, SMS, analytics, etc.). |

### 1.8 Privacy policy / Terms / Refund cancellation / Contact Us / About Us

| Field | Value |
|-------|--------|
| **Status** | **Partially implemented** |
| **Verified (read paths)** | `GET /api/settings?type=…` reads `SystemSetting` ([`student_reads.py`](../app/api/student_reads.py)). Allowed school-settings types include `privacy_policy`, `terms_condition`, `refund_cancellation`, `about_us`, `contact_us`. |
| **Verified (empty school bootstrap)** | `_school_settings_bootstrap` hardcodes empty strings for those fields ([`student_reads.py`](../app/api/student_reads.py) ~253–271). `GET /api/school-settings`, `/api/student/school-settings`, `/api/parent/school-settings` use that bootstrap. |
| **Missing** | School Admin write CMS under `/api/v1/school-admin/...`. Platform `ALLOWED_SETTING_KEYS` does **not** include legal page slugs. `SystemSetting.data` is `String(255)` — unsuitable for long HTML. |

### 1.9 Related platform system settings

| Field | Value |
|-------|--------|
| **Status** | **Fully implemented** (platform) / stub legacy |
| **Verified** | `GET/PATCH /api/v1/super-admin/settings` + tests in `tests/v1/test_phase8_platform.py`. Stub `GET /api/system-settings` → 501 ([`stubs.py`](../app/api/stubs.py)). |

---

## 2. Web Settings

### 2.1 Website content management

| Field | Value |
|-------|--------|
| **Status** | **Partially implemented** |
| **Verified** | `School.school_website` + domain fields (Alembic `20261025_0038`, model in [`tables.py`](../app/models/tables.py)). Sliders/gallery: `/api/v1/school-admin/sliders`, `/gallery` ([`school_admin_mgmt.py`](../app/api/v1/school_admin_mgmt.py), models `SchoolSlider`, `SchoolGalleryItem`). |
| **Missing** | Generic editable web pages / homepage content CMS beyond URL + media. |

### 2.2 FAQ management

| Field | Value |
|-------|--------|
| **Status** | **Missing** |
| **Verified** | `faqs` listed in [`catalog.py`](../app/models/catalog.py) only. No ORM, routes, or Alembic FAQ table. |

---

## 3. Other modules

### 3.1 Database backup and recovery

| Field | Value |
|-------|--------|
| **Status** | **Missing** |
| **Verified** | No backup/restore routes, services, models, or stubs found under `app/`. |
| **Plan default** | Super Admin only (shared Neon). Not a School Admin privilege. |

### 3.2 Contact inquiries

| Field | Value |
|-------|--------|
| **Status** | **Missing** (general contact) |
| **Verified related** | **Admission** inquiries: model `AdmissionInquiry`; CRUD `/api/v1/school-admin/admission-inquiries` ([`school_admin_mgmt.py`](../app/api/v1/school_admin_mgmt.py), [`school_academic_mgmt.py`](../app/services/v1/school_academic_mgmt.py), Alembic `20261027_0039`). **Existing needs testing** (no dedicated focused test file found at audit time). |
| **Do not duplicate** | Contact inquiry ≠ admission inquiry. |

### 3.3 Support tickets / support management

| Field | Value |
|-------|--------|
| **Status** | **Missing** |
| **Verified** | Contact fields only: `School.support_email`, `School.support_phone` ([`tables.py`](../app/models/tables.py)); platform keys `support_email` / `support_phone` in settings service. No ticket/thread models or APIs. |

---

## 4. Adjacent school settings (not on handwritten list)

| Feature | Status | Evidence |
|---------|--------|----------|
| Payroll settings | Existing needs testing | `/api/v1/school-admin/payroll-settings` in [`school_admin_mgmt.py`](../app/api/v1/school_admin_mgmt.py) |
| ID card settings | Existing needs testing | `/id-card-settings` same router |
| Staff QR attendance settings | Existing needs testing | `/staff-qr-attendance-settings` same router |

---

## 5. RBAC and security notes (verified)

| Item | Path / detail |
|------|----------------|
| School Admin permission | `PERM_SETTINGS = "settings.manage"` in [`app/services/v1/rbac.py`](../app/services/v1/rbac.py) |
| No feature-level perms | No dedicated leave-settings / WhatsApp / FAQ / backup permissions |
| Secret masking pattern | `SECRET_SETTING_KEYS` never returned as plaintext on GET ([`settings_service.py`](../app/services/v1/settings_service.py)) — reuse for school secrets |
| Tenant isolation | School Admin deps in [`app/api/v1/deps.py`](../app/api/v1/deps.py) (`require_school_admin`, school installed/active) |

---

## 6. Reuse vs invent

| Reuse | Do not invent / do not duplicate |
|-------|----------------------------------|
| Platform `SystemSetting` + super-admin settings API | Overloading `SystemSetting.data` (255) for school HTML CMS |
| `AdmissionInquiry` for admissions only | Using it as general Contact Inquiry |
| Sliders/gallery for media | Fake FAQ success without persistence |
| SaaS `/api/v1/payments*` | School fee gateway as env-only without school CMS when product needs per-school gateways |
| Secret `configured` flags | Returning WhatsApp/payment tokens in JSON |

---

## 7. Summary counts (handwritten checklist)

| Classification | Features (approx.) |
|----------------|-------------------|
| Fully implemented | Platform system settings (1) |
| Partially implemented | Payment settings, third-party (platform), legal pages (read/empty), web content |
| Missing | Leave settings, additional fields, WhatsApp, online exam terms CMS, email templates, FAQs, DB backup, contact inquiries, support tickets |
| Existing needs testing | Admission inquiries; payroll/ID/QR settings; sliders/gallery |

---

## 8. Dependencies for implementation (informational)

1. Product-owner approval of leave/refund/WhatsApp/ticket/backup business rules (see plan doc).  
2. Additive Alembic after current head (do **not** apply to live Neon without explicit approval).  
3. Encryption key for school secrets (env), distinct from platform settings.  
4. Optional follow-up: wire school CMS content into `_school_settings_bootstrap` so mobile/parent reads stop returning empty strings.
