# School ERP — Security / Isolation Matrix (Backend)

Date: 2026-11-05  
Status: Offline unit coverage + code contracts. Full DB IDOR suite pending isolated DB / approval.

| Case | Expected | Evidence |
|---|---|---|
| School A cannot read School B resources | 403/404 via `auth.user.school_id` | Existing `require_school_admin` + service `_owned` |
| Branch 1 cannot read Branch 2 student | 404 when `X-Branch-Id` + ACL filter | `school_people._owned_student` + `branch_id` |
| Branch admin denied other branch | 403 | `resolve_branch_context` + `v1_user_branch_access` |
| `X-Branch-Id` for foreign school | 403 | `branch.school_id == auth.user.school_id` |
| Trust header alone | Forbidden | Header is hint; ACL always applied |
| Default branch delete | 422 | `soft_delete_branch` |
| Disable default branch | 422 | `update_branch` |
| Duplicate fee payment same idempotency_key | Returns existing row | `collect_fee` |
| Cross-branch fee assignment collect | 404 | `collect_fee` branch check |
| Consolidated reports | Sum of `allowed_branch_ids` only | `report_*` + `X-Branch-Scope: all` |
| Create Branch 2 | Same `school_id`, never new school | `create_branch` |
| Assign admins | UUID `v1_users` only | `set_branch_admins` |

Original 29 QA cases: **BLOCKED** (not in repository).
