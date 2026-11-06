# Branch (second campus) API: what the admin panel needs

For Nitish, from Vishal, 5 Nov 2026. **Status: BLOCKED.** The live backend has no branch concept. There are no branch or campus routes in the OpenAPI (639 paths), and no branch table or `parent_school_id` in the models. The admin panel won't fake branches with browser-only data, so all branch screens wait on this contract.

## Suggested model

**Treat a branch as a school under a parent school.** Add `schools.parent_school_id` (nullable), with **one level only**.

- Each branch is its own tenant with its own `school_id`. Every existing `/school-admin/*` module (students, teachers, classes, attendance, fees, exams, homework, timetable, notices, payroll, transport) then works per branch without changes. Isolation is the existing school scoping.
- The main school's admin can work in any branch, but only after switching. A branch admin is a `school_admin` of the branch school and can't see the parent or sibling branches.

## Super Admin

| Method | Path | Body / result |
| --- | --- | --- |
| GET | `/super-admin/schools/{school_id}/branches` | `{items: Branch[], total}` |
| POST | `/super-admin/schools/{school_id}/branches` | `{name, code, address, city?, state?, postal_code?, support_email, support_phone, status?}` → `Branch` (201). 409 for a duplicate code; 422 field errors as today. |
| GET | `/super-admin/schools/{school_id}/branches/{branch_id}` | `Branch` with `admins[]` and counts (`students`, `teachers`, `classes`) |
| PATCH | `/super-admin/schools/{school_id}/branches/{branch_id}` | Same fields as POST, partial |
| POST | `/super-admin/schools/{school_id}/branches/{branch_id}/activate` and `/deactivate` | `Branch` |
| DELETE | `/super-admin/schools/{school_id}/branches/{branch_id}` | Soft delete. 409 `{detail}` if the branch still has students or payments. |
| POST | `/super-admin/schools/{school_id}/branches/{branch_id}/admins` | New branch admin `{email, password, first_name, last_name, mobile}`, or an existing user `{user_id}` |
| DELETE | `/super-admin/schools/{school_id}/branches/{branch_id}/admins/{admin_id}` | Remove the assignment |

`Branch`: `{id, parent_school_id, name, code, address, city, state, postal_code, support_email, support_phone, status, created_at, updated_at}`. `GET /super-admin/schools/{id}` should also return `parent_school_id` and `branch_count`.

## School Admin

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/auth/me` (extend) | Add `school_id`, `branch_id` (`null` on the main school), `branches: [{id, name, code, status}]` the user may switch to, and `can_switch_branch`. |
| GET | `/school-admin/branches` | Branches this admin may open: the main admin gets all, a branch admin only their own. |
| POST | `/school-admin/branches/{branch_id}/switch` | Returns `{access_token, expires_at, school_id, branch}`. The token is scoped to that branch, so every existing route reads and writes that branch only. The panel swaps tokens; nothing else changes on the frontend. 403 if the user may not open that branch. |
| GET | `/school-admin/branches/summary?session_year_id=` | Main school only. Per branch: `{branch_id, name, students, teachers, classes, exams, attendance_today: {present, absent}, fees_collected_month, fees_outstanding}`, plus a `total` row. Used for the consolidated dashboard. |
| GET | `/school-admin/reports/*?branch_id=all\|{id}` (extend) | Main school only: consolidated or per-branch versions of the existing report routes. Branch admins get their own branch whatever they send. |

## Rules the backend must enforce (the panel only hides buttons)

1. Every `/school-admin/*` route stays scoped to the token's school. A `branch_id`, `school_id` or `X-School-Id` in a request must never widen access.
2. A branch admin gets 403 on sibling branches, the parent school, `/branches/summary` and `branch_id=all`.
3. Files, receipts, report cards, payslips and certificates must check that the owning school matches the token's school.
4. Deleting or deactivating a branch must not touch the parent's or siblings' records.
5. Automated tests:
   - School A cannot read School B, and Branch 2 cannot read Branch 1.
   - Switching works only for allowed branches.
   - Branch 1 data is unchanged after Branch 2 writes.

## What the panel will build once these exist

- **Super Admin:** Branches tab on the school profile (list, add, view, edit, activate/deactivate, delete with confirmation, assign branch admin).
- **School Admin:**
  - a branch switcher in the header (shown only when `can_switch_branch`)
  - every module scoped by the switched token
  - a consolidated dashboard and reports for the main admin
  - branch actions hidden from branch admins
- **Tests:** branch switching, role-based hiding, and an end-to-end flow (add Branch 2 → assign admin → switch → add class, section, student → check Branch 1 unchanged).
