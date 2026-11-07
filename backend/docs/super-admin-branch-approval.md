# Super Admin branch approval and quota

**Status:** implemented in backend code. Migration `20261106_0047` → `20261106_0048` is **not** applied to Neon, Supabase, or production. Admin Web is **not** updated.

## Business workflow

1. Every school keeps one default Main branch (`ensure_default_branch`).
2. New and existing schools default to `branch_creation_enabled = false` and `max_branches = 1`.
3. `max_branches` is the total allowed **active** branches, including Main.
   - `1` = Main only
   - `2` = Main + one more
   - `5` = Main + four more
4. Super Admin reads the branch summary, then sets the cap and turns additional creation on or off.
5. A full School Admin may call `POST /school-admin/branches` only when creation is enabled and the active count is below the cap.
6. Turning creation off does **not** delete, deactivate, or move existing branches.

## Quota rule

Counted rows: `school_branches` with `deleted_at IS NULL` and `status = 1`.

Not counted: inactive branches (`status = 0`) and soft-deleted branches. Deactivating or soft-deleting a branch frees a slot. Lowering `max_branches` below the current **active** count is rejected (422). Existing rows are left as they are.

`remaining_capacity = max(0, max_branches - active_branches)`.

`can_create_branch` is true only for a full `school_admin` when creation is enabled and `active_branches < max_branches`. Branch admins are always false.

## Database

| Column | Table | Type | Default |
|---|---|---|---|
| `branch_creation_enabled` | `schools` | boolean NOT NULL | `false` |
| `max_branches` | `schools` | integer NOT NULL | `1` |

Check constraint: `ck_schools_max_branches_at_least_one` (`max_branches >= 1`).

Migration file: `alembic/versions/20261106_0048_school_branch_quota.py`.  
Parent: `20261106_0047`. Single head: `20261106_0048`.  
The migration only adds columns and the check. It does not write `school_branches`.

**Do not apply this migration until staging approval.**

## API

All Super Admin routes use `require_super_admin`. School id comes from the path. School Admin routes take `school_id` from `auth.user.school_id` only.

### `GET /api/v1/super-admin/schools/{school_id}/branches`

```json
{
  "school_id": 10,
  "school_name": "Hill School",
  "total_branches": 2,
  "active_branches": 1,
  "inactive_branches": 1,
  "max_branches": 3,
  "remaining_capacity": 2,
  "branch_creation_enabled": true,
  "branches": [
    {
      "id": 1,
      "school_id": 10,
      "name": "Main",
      "code": "MAIN",
      "address": "",
      "status": 1,
      "is_default": true,
      "deleted_at": null,
      "created_at": null,
      "student_count": 4,
      "teacher_count": 2
    }
  ]
}
```

`student_count` is non-deleted `students` on that branch. `teacher_count` is `staffs` rows on that branch (the same staff proxy used by teacher reports).

### `PATCH /api/v1/super-admin/schools/{school_id}/branch-settings`

```json
{ "max_branches": 3, "branch_creation_enabled": true }
```

Returns the same summary shape. Unknown school: 404. `max_branches < 1`: 422. Cap below the active count: 422.

`PATCH /api/v1/super-admin/schools/{school_id}` still rejects these fields (`extra=forbid`). School Admin has no route that can set them.

`GET /api/v1/super-admin/schools/{school_id}` now also includes `branch_creation_enabled` and `max_branches` on the school object.

### School Admin

`POST /api/v1/school-admin/branches` is unchanged in path and body (`name`, `code`, `address`).

- Creation disabled: **403** `Branch creation is not enabled for this school`
- Active count already at `max_branches`: **403** `Branch limit reached`
- Duplicate name: **409**
- Another school's branch id: **404**

`GET /api/v1/school-admin/me/branches` keeps `branches`, `default_branch_id`, `active_branch_id`, `is_full_school_admin`, and adds:

- `total_branches`, `active_branches` (school-wide, not only the caller's list)
- `max_branches`, `remaining_capacity`, `branch_creation_enabled`, `can_create_branch`

The `branches` array is still limited to branches that user may access.

## Authorization

| Action | Who |
|---|---|
| Read or change quota | Super Admin only |
| Create an additional branch | Full `school_admin` with `school.manage`, and only inside the quota |
| Branch admin create | Denied (`school.manage` is not on `branch_admin`) |

## Concurrency

`create_branch` and `update_branch_settings` lock the `schools` row (`SELECT … FOR UPDATE`) and perform the count plus insert in that transaction. A second create waits, then sees the new active count. Failure rolls back, including a Main branch that was only flushed because the school had none yet.

`ensure_default_branch` (list, `/me`, branch context) may still create the single Main branch when a school has no branches. It does not create a second branch and does not turn on additional creation. It is not a public bypass of Super Admin approval.

## Frontend handoff (Nitish)

Do not show Add Branch unless `can_create_branch` is true on `GET /api/v1/school-admin/me/branches`. The button is not sufficient: the POST still returns 403.

Super Admin school profile should call:

- `GET /api/v1/super-admin/schools/{id}/branches`
- `PATCH /api/v1/super-admin/schools/{id}/branch-settings`

Admin Web was not changed in this pass.

## Staging check (after an approved migrate)

1. Confirm Alembic is at `20261106_0048` on an isolated database, not production.
2. Existing schools show `branch_creation_enabled=false`, `max_branches=1`, and their Main branch still present.
3. School Admin POST of a second branch returns 403.
4. Super Admin sets `max_branches=2` and `branch_creation_enabled=true`.
5. School Admin creates one branch, then the next POST returns 403.
6. Super Admin sets `branch_creation_enabled=false`. Both branches still exist.
7. Two parallel creates with one slot left produce one 201 and one 403.
