# School Admin Six-Feature Implementation Plan

Date: 2026-10-29  
Source of truth: repository code + `OPERATIONS_MODULES_API_CONTRACT.md` + feature audit.  
Safety: no Neon apply, no Render deploy, no admin-web, no git push.

## Feature matrix

| Feature | Required | Existing | Missing | Reuse | New | Migration | Security | Tests | Acceptance |
|---------|----------|----------|---------|-------|-----|-----------|----------|-------|------------|
| Live bus | Admin live map poll | GPS write, trips, parent live | `GET vehicle-locations`, trip detail+GPS | `school_erp_transport`, erp routes | Read helpers + schemas | None | `PERM_SCHOOL`, school_id filter | OpenAPI + freshness unit | Admin sees school-only GPS + freshness |
| Payroll | Server calc, payslips | Settings, runs (client $), components | Structures, assign, preview/process, payslip PDF | mgmt fees auth, FPDF | `school_erp_payroll`, routes | 0043+ structures/assign/payslip cols | `PERM_FEES`, period lock | Calc + idempotency offline | Process rejects dupes; payslip from DB |
| Announcements | Draft/audience/publish | GET/POST basic | status, audience, PATCH/DELETE, lazy publish | mgmt announcements | Columns + services | Alter announcements | Drafts admin-only; recipients filtered | Lifecycle offline | Draft→publish; audience filter |
| Messaging | Teacher↔parent chat | None (501 stubs) | Full domain | StudentGuardian, TeacherAssignment | Models, service, admin+portal routes | messaging_* tables | Membership on every op; admin moderate via policy | Authz offline | Authorized exchange only |
| Leave types | Typed CRUD + leave FK | Opaque leave-settings | leave_types table, leave_type_id | settings + academics leaves | CRUD + balances derive | leave_types + FK | School-scoped codes | CRUD + FK validation | Types school-owned; leave refs valid |
| Staff certs | Issue staff + PDF + QR verify | Student issue, ID-card JSON | staff_id, token, PDF, verify | templates, FPDF | issue-staff, list, pdf, public verify | cert issue cols | Token unguessable; minimal public | Issue/revoke/verify offline | Admin issues; public verifies without PII |

## Order

1. Live bus (no migration)  
2. Leave types  
3. Announcements  
4. Staff certificates  
5. Payroll  
6. Messaging  
7. Offline tests + reports  

## Locked decisions

See approved Cursor plan: polling GPS; payroll formula from structures (no statutory tax); lazy announcement publish; messaging text-first; leave balances derived; cert QR = opaque verify URL.
