# Backup and restore — Phase 2 operational design

## Scope

Parity with Laravel jobs:

- `GenerateSchoolBackupJob` / `GenerateSuperAdminBackupJob`
- `RestoreSchoolBackupJob` / `RestoreSuperAdminBackupJob`
- Schedule `app:delete-old-backups` (daily retention cleanup)

Backups include **MySQL dumps** and must remain consistent with **shared media** under `/storage` (document whether school backups embed files or rely on volume snapshots).

---

## Drill requirements (gate)

A Phase 2 design is incomplete until these drills are scheduled and owned. Execution can land in Phase 7/9, but the runbook must exist now.

### Drill A — School backup/restore (staging)

| Step | Pass criteria |
| --- | --- |
| 1. Pick fixture tenant with known row counts + one media file checksum | Baseline recorded |
| 2. Generate school backup via owning stack | Artifact on shared storage; admin download URL uses frozen origin |
| 3. Mutate tenant (delete row, replace file) | Divergence confirmed |
| 4. Restore backup with `lock:restore:school:{id}` | Single-flight; second restore blocked |
| 5. Verify row counts, critical fee/attendance tables, media checksum | Match pre-backup |
| 6. App login + one read API for that school | Sanctum token behavior documented (may invalidate — record actual Laravel behavior) |

**RTO target (design placeholder):** restore single school ≤ **60 minutes** from decision to verify (fill measured value after first drill).  
**RPO target (placeholder):** ≤ **24 hours** or last successful backup (align with product).

### Drill B — Super-admin / central backup

| Step | Pass criteria |
| --- | --- |
| Backup central DB | Completes; secrets not logged |
| Restore to isolated staging central | Schools list + package rows intact |
| Cross-check tenant DB names still resolve | No orphan pointer |

### Drill C — Retention

| Step | Pass criteria |
| --- | --- |
| Seed backups older than retention | Present |
| Run `delete-old-backups` equivalent | Only expired removed; newest retained |
| Confirm active restore artifact not deleted | Guardrails hold |

### Drill D — Canary rollback interaction

| Step | Pass criteria |
| --- | --- |
| FastAPI owns backup generate; rollback API to Laravel | Laravel can still download/restore artifacts written by FastAPI (shared storage) |
| Inverse | Same |

---

## Operational rules

1. **Never** restore production without explicit operator confirmation + backup of current state (`pre_restore_*`).
2. Restores are **exclusive**: distributed lock + maintenance flag for that school if Laravel has one.
3. Backup files live on shared storage ([STORAGE.md](STORAGE.md)); paths stable across stacks.
4. Credentials in dumps: production dumps are restricted; sanitized copies only in `datasets/` / fixtures.
5. Schedule ownership: only one stack runs `app:delete-old-backups`.
6. Monitor disk usage; alert before backup volume fills.

---

## Documentation outputs after each drill

Store under `ops/cutover/drills/YYYY-MM-DD-backup-restore.md`:

- Duration, RTO/RPO measured
- Failures and fixes
- Approver sign-off

---

## Acceptance pointers

All four drills signed once before Phase 9 production canary of backup/restore admin modules. See [ACCEPTANCE_TESTS.md](ACCEPTANCE_TESTS.md).
