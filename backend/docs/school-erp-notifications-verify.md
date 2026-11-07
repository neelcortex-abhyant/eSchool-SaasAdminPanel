# School ERP — Notifications / Auth email verify

Reuse only: [`notification_delivery.py`](../app/services/v1/notification_delivery.py) (gap-closure). Do not add parallel send APIs.

| Flow | Backend status | Env blockers |
|---|---|---|
| Leave decision notify | Enqueues with idempotency | FCM/SMTP optional |
| Fee reminder | Enqueues `fee_reminder:{school}:{assignment}` | Same |
| Homework created | Enqueues event | Same |
| Exam publish / results | Enqueues | Same |
| Absence | Enqueues | Same |
| Registration confirmation | Existing registration service | SMTP must be configured for real delivery |
| Password reset | Existing auth reset tokens | SMTP / reset URL env |

Branch stamp: operational enqueue paths should pass school_id (existing). When recipient is branch-scoped, notifications table has nullable `branch_id` after migration 0046 — stamp when known.

No fake "sent" without queue (gap-closure guarantee preserved).
