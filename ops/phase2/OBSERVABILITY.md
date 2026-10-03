# Observability — Phase 2 operational design

## Structured logs

Every HTTP request and job log line should include:

| Field | Source |
| --- | --- |
| `timestamp` | ISO-8601 UTC |
| `level` | info/warn/error |
| `message` | Short event name |
| `request_id` | Generated at proxy or app edge; echo as `X-Request-Id` response header |
| `school_id` / `school_code` | When resolved (never log full payment secrets) |
| `user_id` / `role` | When authenticated |
| `route` / `method` | Normalized path template |
| `owner` | `laravel` \| `fastapi` (from proxy or app) |
| `latency_ms` | Request or job duration |
| `http_status` / `body_code` | Preserve business `code` for Flutter logout semantics |
| `job_name` / `job_id` / `attempt` | Workers |

**Redact:** passwords, tokens (bearers, Sanctum plains), webhook secrets, raw webhook bodies (log hash + event id only), FCM server keys, `APP_KEY`, card data.

---

## Metrics (minimum)

| Metric | Labels | Notes |
| --- | --- | --- |
| `http_requests_total` | route, method, status, owner, school_cohort | |
| `http_request_duration_seconds` | route, owner | Histogram |
| `mysql_pool_in_use` / `mysql_pool_wait` | pool=`central`\|`tenant` | Guard exhaustion |
| `queue_depth` | queue_name, owner | |
| `queue_job_duration_seconds` | job_name | |
| `queue_dlq_depth` | queue_name | Alert > 0 critical |
| `cache_ops_total` | op, result | |
| `payment_webhook_total` | gateway, result=`ok\|bad_sig\|duplicate\|error` | |
| `attendance_finalize_schools` | result | Per tick |
| `realtime_publish_total` | event, result | |

Export Prometheus (or equivalent). Wire dashboards under `ops/monitoring/` in Phase 3+.

---

## SLOs (placeholders — fill after Laravel baseline)

From [baseline/LIMITS_AND_BASELINE.md](../../baseline/LIMITS_AND_BASELINE.md); owners assign numbers before Phase 9.

| SLO | Laravel baseline | FastAPI target | Alert |
| --- | --- | --- | --- |
| Login p95 | TBD | ≤ baseline + agreed budget | Page on burn |
| Authenticated read p95 | TBD | ≤ baseline + budget | |
| Authenticated write p95 | TBD | ≤ baseline + budget | |
| HTTP 5xx rate | TBD | ≤ baseline | Immediate |
| Business-error rate (body codes) | TBD | parity | Ticket |
| Webhook success (valid sig) | TBD | ≥ 99.9% excluding provider outages | |
| Queue oldest age | TBD | No dual-consumer lag | |
| Student-web under 10s | pass/fail | pass | |
| 50 MB upload success | pass/fail | pass | |

Error budget policy: freeze canary expansion when FastAPI 5xx or body-code regression exceeds budget for 1h.

---

## Request and school IDs

1. Reverse proxy generates `X-Request-Id` if missing; forwards to Laravel/FastAPI.
2. App logs the same id; workers receive `request_id` in enqueue payload when spawned from HTTP.
3. `school_code` / `school_id` attached after tenant resolution middleware.
4. Support can paste request id → find logs across proxy, API, worker, and payment webhook processing.

---

## Tracing (optional Phase 3+)

OpenTelemetry trace across proxy → FastAPI → MySQL/Redis. Not required to close Phase 2 design gate; recommended before Phase 9.

---

## Alert routing (placeholders)

| Severity | Examples | Channel |
| --- | --- | --- |
| P1 | Payment webhook error spike, DLQ critical, MySQL pool exhaustion, canary 5xx | On-call |
| P2 | Queue age, finalize failures per school, FCM failure rate | Biz-hours |
| P3 | Elevated latency vs baseline | Ticket |

---

## Acceptance pointers

Emit request_id on a sample FastAPI route; verify school_id present on tenant routes; confirm redaction on login logs; metrics endpoint scraped in staging.
