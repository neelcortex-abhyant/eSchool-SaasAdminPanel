# Queue and cron — Phase 2 operational design

## Decision

| Layer | Choice | Notes |
| --- | --- | --- |
| Broker | **Shared Redis** (same instance Laravel uses during canary) | Separate logical key prefixes; see [CACHE_AND_REDIS.md](CACHE_AND_REDIS.md) |
| Workers | **ARQ** (async Redis queue) on FastAPI | Primary recommendation |
| Scheduler | **Dedicated scheduler process** (`python -m app.scheduler` or system cron → CLI) | Mirrors Laravel `Kernel::schedule`; not in-request |
| Locks | Redis `SET key NX PX` / Redlock-equivalent | Parity with `withoutOverlapping` and job uniqueness |

### Why Redis + ARQ (not Celery as default)

| Criterion | ARQ + Redis | Celery + Redis |
| --- | --- | --- |
| Fits FastAPI asyncio | Native async jobs; tenant DB sessions stay request/job-scoped | Sync workers need careful thread/process isolation |
| Ops surface during canary | One Redis already required for cache/queues/Reverb pub | Same broker, heavier worker + Beat stack |
| Retry / DLQ | Explicit job wrappers + dead-letter list (documented below) | Built-in retry; still need custom DLQ and tenant context |
| Team cost | Smaller Python surface for this migration | Prefer if ops already run Celery at scale |

**Fallback:** Celery + Redis + Celery Beat is acceptable if human review prefers its maturity. Either way: **one owner per logical job**; never dual-consume Laravel Horizon/queue workers and FastAPI workers for the same job name.

Do not introduce RabbitMQ/SQS for Phase 2–9 canary; keep the shared Redis topology.

---

## Laravel inventory to replace (one owner each)

### Scheduled commands (`app/Console/Kernel.php`)

| Laravel command | Cadence | Lock / uniqueness | Transfer notes |
| --- | --- | --- | --- |
| `subscriptionBill:cron` | daily | Exactly-once per calendar day (UTC or app TZ — record in ledger) | SaaS billing; idempotent by bill period + school |
| `notifications:delete` | monthly | Safe cleanup | Delete only expired rows matching Laravel criteria |
| `transport:expiry-reminder` | daily | Per school + date | FCM/email side effects; one owner |
| `app:delete-old-backups` | daily | Retention policy | Shared backup disk/object store |
| `whatsapp:process-scheduled` | everyMinute | Prefer `withoutOverlapping` when FastAPI owns it | Laravel currently runs **without** `withoutOverlapping` — FastAPI must add lock |
| `staff-attendance:finalize` | everyMinute | `withoutOverlapping` today | School-local TZ; see below |
| `staff-attendance:purge-punches` | monthlyOn(1, 01:00) | Finalized attendance never deleted | Raw punches only |

Also preserve HTTP cron surface if still used in production: `GET /subscription/cron-job` (`Controller@cron_job`) — classify as open helper; either proxy to FastAPI after ownership transfer or keep on Laravel until retired with approval.

### Queued jobs (`app/Jobs/`)

| Job | Side effects | Idempotency key suggestion |
| --- | --- | --- |
| `SetupSchoolDatabase` | CREATE DATABASE, migrate, seed | `provision:{school_id}:{run_id}` |
| `MigrateSchoolDatabaseJob` | Tenant DDL via Laravel migrator | `tenant_migrate:{school_id}:{migration}` |
| `SchoolDatabaseSeederJob` | Seed | `seed:{school_id}:{run_id}` |
| `ProcessAcademySetupWizardJob` | Wizard steps + Reverb progress | `academy:{school_id}:{run_id}:{step}` |
| `ProcessSchoolUpdateJob` / `ProcessSystemUpdateJob` | Per-school / system update | `update:{run_id}:{school_id}` |
| `GenerateSchoolBackupJob` / `GenerateSuperAdminBackupJob` | Files on shared storage | `backup:{scope}:{id}:{requested_at}` |
| `RestoreSchoolBackupJob` / `RestoreSuperAdminBackupJob` | Destructive restore | `restore:{scope}:{id}:{requested_at}` — single-flight lock |
| `SessionYearMigrationJob` | Academic year cutover | `session_year:{school_id}:{from}:{to}` |
| `SendFcmNotification` | FCM HTTP | `fcm:{notification_id}` or hash of payload+tokens |
| `SendWhatsAppJob` | Meta Cloud API | `wa:{school_id}:{message_id\|schedule_id}` |
| `SendBulkStudentEmail` / `SendBulkStaffEmail` | SMTP | `email_bulk:{batch_id}` |
| `BulkNotificationsJobv3_0_0` | Multi-channel | `bulk_notif:{batch_id}` |
| `SendMissingPunchOutReport` | Email after finalize | Claim `StaffAttendanceReportLog` row before send (Laravel already does) |

---

## Worker runtime rules

1. **Tenant context:** Every job payload carries immutable `school_id` and/or `database_name`. Worker opens its own tenant session; never reuse a global engine from a previous job.
2. **Central vs tenant:** Provisioning/billing jobs use central `mysql`; school data jobs switch after resolving `schools.database_name`.
3. **Shutdown:** ARQ workers drain in-flight jobs (graceful SIGTERM). Do not kill mid-DDL/restore.
4. **Concurrency:** Cap concurrent tenant connections (bounded pool). Prefer school-sharded concurrency limits for finalize and WhatsApp.
5. **Observability:** Log `job_name`, `job_id`, `school_id`, `attempt`, `lock_key`, `request_id` if enqueued from HTTP.

---

## Retries and backoff

| Class | Max attempts | Backoff | Examples |
| --- | --- | --- | --- |
| Transient provider | 5 | Exponential: 30s, 2m, 8m, 30m, 2h (+ jitter) | FCM, WhatsApp, SMTP, gateway API |
| Transient infra | 8 | Exponential capped at 15m | Redis blip, MySQL deadlock/lock wait |
| Business / validation | 0 retries | Dead-letter immediately | Bad payload, missing school, invalid signature already handled at HTTP |
| Destructive / DDL | 1 automatic retry max; then DLQ + human | Manual resume via tenant ledger | Provision migrate/seed, restore |

On final failure: push to Redis list `arq:dlq` (or Celery equivalent) with full payload + exception; alert on depth > 0 for critical queues (`provision`, `payments`, `attendance_finalize`, `billing`).

---

## Idempotency

- Store processed markers in Redis (`job:done:{idempotency_key}`, TTL ≥ 7 days) **or** rely on DB unique constraints / status columns (preferred for money and attendance).
- Payment-related async work must key off `payment_transactions.id` + terminal status transitions only.
- `SendMissingPunchOutReport`: claim `StaffAttendanceReportLog` before SMTP (parity with Laravel).
- Re-enqueue after crash must not double-finalize attendance for the same `(school_id, date)`.

---

## Dead-letter

| Field | Required |
| --- | --- |
| `job_name`, `payload`, `error`, `traceback` | yes |
| `school_id`, `attempt`, `first_failed_at`, `last_failed_at` | yes |
| `owner` (`fastapi` \| `laravel`) | yes during canary |
| Replay tool | CLI `jobs replay --dlq-id=…` that re-checks idempotency key |

Never auto-replay restore or DDL DLQ without operator flag.

---

## Distributed locks

| Lock key pattern | TTL | Used by |
| --- | --- | --- |
| `lock:schedule:staff-attendance:finalize` | 55s | Global schedule mutex (Laravel `withoutOverlapping`) |
| `lock:attendance:finalize:{school_id}:{date}` | 10m | Per-school finalize |
| `lock:schedule:whatsapp:process` | 55s | WhatsApp minute runner |
| `lock:schedule:subscriptionBill:{date}` | 23h | Daily billing |
| `lock:provision:{school_id}` | 1h | School DB create/migrate/seed |
| `lock:restore:{scope}:{id}` | 2h | Backup restore single-flight |
| `lock:domain:{domain}:owner` | n/a (config) | Ownership matrix — not a runtime lock; enforced by proxy + disabled Blade |

Lock acquisition failure → skip this tick (schedules) or requeue with delay (jobs). Do not proceed without the lock.

---

## Staff attendance finalization (school-local timezone)

Parity requirements from Laravel `FinalizeStaffAttendance` + `AttendanceFinalizationService`:

1. Load active installed schools from central DB (`status=1`, `installed=1`).
2. Per school: connect to `database_name`; skip if QR attendance disabled.
3. Resolve attendance **date** with `schoolNow(school_id)` (school `time_zone` → system setting → `app.timezone`), not server UTC date alone.
4. Due when `schoolNow >= date + qr_attendance_school_end_time + 1 hour` in school TZ (`isDue`).
5. Finalize once per `(school_id, date)`; subsequent minute ticks are no-ops for already finalized rows.
6. On missing punch-outs: dispatch report job only if `StaffAttendanceReportLog` not already handled.
7. One school failure must not abort the loop.

**Canary rule:** While Laravel owns `staff-attendance:finalize`, FastAPI must not run it (even in shadow that writes). Shadow may compute “would finalize” metrics only with read-only DB and no locks that block Laravel.

---

## One-owner transfer rule (vs Laravel)

From the canary ownership matrix:

> API, admin, webhook, queue, cache invalidation, and schedule ownership for a domain move as **one lifecycle**.

Concrete transfer checklist for any job/schedule:

1. Ownership matrix row approved (`Worker/schedule` column → FastAPI).
2. Laravel schedule entry **disabled** (comment out / feature flag) in the same deploy window as FastAPI enable.
3. Laravel queue workers **stop consuming** that job class (remove dispatch sites or guard with `owner === laravel`).
4. Drain Laravel queue depth for that job to zero.
5. Enable FastAPI consumer/scheduler.
6. Verify single lock holder in Redis for 24h.
7. Rollback = re-enable Laravel schedule/worker and disable FastAPI consumer (RTO in [DEPLOYMENT_AND_ROLLBACK.md](DEPLOYMENT_AND_ROLLBACK.md)).

**Forbidden:** FastAPI mobile fee writes + Laravel `subscriptionBill` / webhook for the same money domain; FastAPI chat writes + Laravel broadcast path for the same messages without a reviewed proof.

---

## Queue naming

| Logical queue | Redis / ARQ queue name | Owner during baseline |
| --- | --- | --- |
| default | `laravel` / `default` | Laravel |
| FastAPI default | `fastapi:default` | unused until transfer |
| FastAPI critical | `fastapi:critical` | provision, restore, billing |
| FastAPI notify | `fastapi:notify` | FCM, WhatsApp, email |
| FastAPI attendance | `fastapi:attendance` | finalize + punch reports |

Keep Laravel queue names untouched until a domain transfers; then stop Laravel producers for that domain.

---

## Acceptance pointers

See [ACCEPTANCE_TESTS.md](ACCEPTANCE_TESTS.md) § Queues & schedules. Gate for this doc: human review sign-off before Phase 3 implements workers.
