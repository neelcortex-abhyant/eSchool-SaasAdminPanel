# Provisioning and migrations — Phase 2 operational design

## Goals

1. School provisioning (create DB → migrate → seed → welcome) matches Laravel jobs.
2. Future schema changes use a **resumable tenant ledger**, not ad-hoc ORM DDL.
3. **No production DDL from FastAPI ORM** (`create_all`, Alembic autogenerate against prod, prototype `create_schema()`, etc.).

Baseline schema: v1.11 fingerprint in [baseline/SCHEMA_FINGERPRINT.md](../../baseline/SCHEMA_FINGERPRINT.md). Do not regenerate the schema from scratch.

---

## School provision pipeline (parity)

Laravel jobs to map 1:1:

| Step | Laravel artifact | FastAPI owner when transferred |
| --- | --- | --- |
| Create database | `SetupSchoolDatabase` | Critical queue + `lock:provision:{school_id}` |
| Run migrations | `MigrateSchoolDatabaseJob` | Same lock; ledger rows per migration |
| Seed | `SchoolDatabaseSeederJob` | Idempotent seeds where possible |
| Academy wizard | `ProcessAcademySetupWizardJob` | Progress via Reverb `school.{id}` |
| System/school updates | `ProcessSystemUpdateJob` / `ProcessSchoolUpdateJob` | Per-run finalize when all schools done |
| Session year migration | `SessionYearMigrationJob` | Academic cutover |

Broadcast progress with exact payload from [REALTIME.md](REALTIME.md) (`school.provision.progress`).

Central DB updates (`schools.installed`, status, database_name) commit only after successful steps; failures set `failed` progress and leave ledger resumable.

---

## Resumable tenant ledger

Maintain tables (or extend existing Laravel update-run tables if already present) conceptually:

| Column | Purpose |
| --- | --- |
| `id` / `run_id` | Provision or migration run |
| `school_id` | Tenant |
| `database_name` | Immutable once assigned |
| `step` | `create_db` \| `migrate` \| `seed` \| `post` \| … |
| `migration_name` | For migrate steps |
| `status` | `pending` \| `running` \| `completed` \| `failed` \| `skipped` |
| `attempt` | Retry count |
| `started_at` / `finished_at` | Timing |
| `error` | Last error (truncated, no secrets) |
| `backup_ref` | Pre-migrate backup id when required |

**Resume rules:**

1. Re-running a provision continues from first non-`completed` step.
2. `CREATE DATABASE` is skipped if DB exists and ledger says create completed.
3. Migrations run in filename order; never mark complete without success.
4. Failed school does not block other schools in a multi-tenant update run.
5. Operator CLI: `ledger status`, `ledger resume --school=`, `ledger abort` (no silent reset).

---

## No production DDL from FastAPI ORM

| Allowed | Forbidden in production |
| --- | --- |
| Apply versioned SQL/Alembic revision files via explicit migrator job | `Base.metadata.create_all()` on startup |
| Laravel `php artisan migrate` while Laravel owns provision | Autogenerate migrations against live prod |
| Read-only SQLAlchemy models matching fingerprint | “Fixup” ALTER from request handlers |
| Documented emergency DDL runbook with backup | Prototype scaffold DDL helpers |

Startup must refuse to boot if a config flag `ALLOW_ORM_DDL=true` is set in production.

---

## Connection and safety

- Provisioning uses a privileged MySQL account only inside worker processes (not the public API pool).
- API request pools remain bounded and non-DDL.
- Always take a backup (or snapshot) before mass tenant migrations ([BACKUP_RESTORE.md](BACKUP_RESTORE.md)).
- SQL mode, `utf8mb4`, and collation must match Laravel baseline.

---

## Canary ownership

Provisioning is a single domain: API trigger, admin UI, workers, and progress channels transfer together. Do not let Next.js admin call FastAPI provision while Laravel jobs still create DBs for the same school id space.

---

## Acceptance pointers

E2E: create school on staging → DB exists → migrations fingerprint matches → seed smoke → progress events → welcome email job enqueued. Resume after injected failure at migrate step. Confirm API process user cannot `CREATE TABLE`.
