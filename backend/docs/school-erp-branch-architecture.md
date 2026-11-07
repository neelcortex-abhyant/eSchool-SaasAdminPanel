# School ERP — Multi-Branch Architecture

Date: 2026-11-05  
Status: Implementation in progress  
Head before this work: `20261030_0045`  
Planned revision: `20261105_0046_school_branches`

## Locked rules

- Branch 2 belongs to the **same** `schools` row (never a second school).
- Auth identity for ACL: **`v1_users.id` (UUID)** only — table `v1_user_branch_access`.
- Isolation: validate `auth.user.school_id` + authorized `branch_id`; never trust `X-Branch-Id` alone.
- Default Branch 1 + backfill: idempotent; downgrade **destroys** Branch 2 separation.
- Do **not** apply this migration to production Neon without explicit approval.

## New tables

### `school_branches`

| Column | Type | Notes |
|---|---|---|
| id | serial PK | |
| school_id | int FK → schools.id | |
| name | varchar(255) | |
| code | varchar(64) nullable | |
| address | varchar(512) default '' | |
| status | int default 1 | 1=active, 0=disabled |
| is_default | int default 0 | at most one per school among non-deleted |
| deleted_at | timestamptz nullable | soft delete |
| created_at / updated_at | timestamptz | |

### `v1_user_branch_access`

| Column | Type | Notes |
|---|---|---|
| user_id | UUID FK → v1_users.id ON DELETE CASCADE | same identity as AuthContext |
| branch_id | int FK → school_branches.id | |
| access_role | varchar(32) | e.g. `branch_admin` |
| created_at | timestamptz | |
| PK | (user_id, branch_id) | |

## Branch-scoped tables (add `branch_id`)

See plan inventory B. Core migration covers operational tables listed in `20261105_0046_school_branches.py` (`BRANCH_SCOPED_TABLES`).

School-scoped catalogs (classes, sections, subjects, session_years, fee_types, CMS, SaaS billing) do **not** get `branch_id` in this revision.

## Request context

Header `X-Branch-Id` is a hint. Pipeline:

1. `require_school_admin` → server `school_id`
2. Resolve branch (header or school default)
3. `branch.school_id == auth.user.school_id`
4. ACL: full school_admin → all school branches; else `v1_user_branch_access`
5. Services filter/write with `(school_id, branch_id)`
6. Related FKs must match the same branch

## Downgrade risk

Dropping `branch_id` / branch tables makes Branch 2 rows indistinguishable from Branch 1. **Not for production.** Requires backup restore to recover separation.
