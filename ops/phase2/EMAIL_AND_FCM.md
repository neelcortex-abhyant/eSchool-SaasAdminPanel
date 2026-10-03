# Email and FCM — Phase 2 operational design

## Goal

Behavioral parity with Laravel mail + Firebase Cloud Messaging so Flutter and student-web notification UX does not change. No client field renames.

---

## FCM parity notes

### Token fields (contract-locked)

| Field | Clients | Behavior |
| --- | --- | --- |
| `fcm_id` | Flutter student/parent/staff login & updates | Store exactly as Laravel; used for push |
| `device_id` | Logout / device cleanup | Remove tokens for that device |
| `web_fcm` | Student-web | Web push token branch on logout/login paths that accept it |
| Legacy `users.fcm_id` | Older clients | Clear on applicable logout variants |

Logout fixtures (Phase 1 templates L1–L4) define cleanup combinations — FastAPI must match row-level side effects and Sanctum token revocation (current token only unless Laravel revokes more).

### Send path

| Laravel | FastAPI target |
| --- | --- |
| `SendFcmNotification` job | ARQ/Celery job on `fastapi:notify` |
| NotificationService / bulk jobs | Same fan-out rules; channel failure must not break the business transaction that enqueued the notify |

### Payload parity

- Preserve notification title/body sources (including localized `trans()` strings where Laravel localizes).
- Preserve data payload keys Flutter already handles (do not rename to `message_type` etc. without client release).
- Respect school/user notification preferences and feature flags as Laravel does.
- Invalid/expired tokens: remove or mark the same way Laravel’s failure handler does (inventory in Phase 3 from job code).

### Config

- `GET /api/firebase-config` remains a public helper — same JSON shape.
- Server credentials (service account / server key) stay server-side; never echo into API responses beyond what Laravel already returns in firebase-config.

### Ownership

FCM send jobs transfer with the domain that enqueues them (attendance, fees, chat, transport reminders). Do not run Laravel and FastAPI consumers for `SendFcmNotification` equivalents simultaneously.

---

## Email parity notes

### Jobs

| Job | Purpose |
| --- | --- |
| `SendBulkStudentEmail` | Bulk student mail |
| `SendBulkStaffEmail` | Bulk staff mail |
| `SendMissingPunchOutReport` | Post-finalize attendance report |
| Welcome / reset / verification mails | Auth and provisioning flows |

### SMTP / mailer

- Reuse the same SMTP/API credentials as Laravel `.env` (`MAIL_*`).
- From address, reply-to, and HTML templates must match production content for canary schools (or explicitly approved template port).
- Absolute links inside emails use frozen `APP_URL` / public origins — never `:8001`.

### Idempotency

- Bulk batches keyed by `batch_id`.
- Missing punch-out report: claim `StaffAttendanceReportLog` before send.
- Password reset: same token table semantics and expiry as Laravel.

### Failure handling

- Transient SMTP → retry with notify backoff ([QUEUE_AND_CRON.md](QUEUE_AND_CRON.md)).
- Permanent failure → DLQ + admin-visible error where Laravel surfaces one.
- Never roll back fee/attendance DB commits because mail failed after commit (match Laravel “notify after success” pattern).

---

## WhatsApp adjacency

WhatsApp is a parallel channel via `SendWhatsAppJob` / `whatsapp:process-scheduled`. See [PAYMENTS_AND_WEBHOOKS.md](PAYMENTS_AND_WEBHOOKS.md) for webhooks and [QUEUE_AND_CRON.md](QUEUE_AND_CRON.md) for the minute scheduler. Email/FCM designs must not assume WhatsApp success.

---

## Acceptance pointers

- Golden logout fixtures clear the correct FCM rows.
- Enqueue FCM from a FastAPI-owned domain; device receives comparable payload.
- Bulk email dry-run compares recipient sets to Laravel for a fixture school.
- No provider secrets in logs (see [OBSERVABILITY.md](OBSERVABILITY.md)).
