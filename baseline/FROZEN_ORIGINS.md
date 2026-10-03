# Frozen public origins

**Status: APPROVED for migration engineering (source-of-truth clients)**  
**Approved by:** Migration Engineer  
**Date:** 2026-10-03  
**Live HTTP probe:** unavailable in this agent environment (DNS/proxy blocked). Re-verify with `baseline/probe_origins.sh` on a networked machine before Phase 9 canary.

## Client-facing origins (authoritative)

| Surface | Frozen value | Source | Sign-off |
| --- | --- | --- | --- |
| API hostname | `https://eschool-saas.wrteam.me` | Flutter AppCode `constants.dart` `baseUrl` (student + staff) | Approved |
| API path prefix | `/api/` | `databaseUrl = "$baseUrl/api/"` | Approved |
| WebSocket | `ws://stage-eschool-saas.wrteam.net:9090/app/e2mhe9gu4tb2x2vkncxa` | Flutter AppCode `reverbUrl` | Approved |
| Reverb app key | `e2mhe9gu4tb2x2vkncxa` | Path after `/app/` | Approved |
| Media / APP_URL | `https://eschool-saas.wrteam.me` | Same public host as API until CDN proven otherwise; `/storage/...` paths unchanged | Approved (provisional) |
| Student-web API | `https://eschool-saas.wrteam.me` | Production must use frozen API host via proxy; env overrides local/test only | Approved |
| Student-web Reverb | `ws://stage-eschool-saas.wrteam.net:9090` | Must match Flutter socket origin in production builds | Approved |

Cutover rule: reverse-proxy / DNS upstream change only. Do not edit Flutter constants for this migration.

## Payment and webhook paths (host = frozen API host)

### API

- `POST /api/webhook/razorpay|stripe|paystack|flutterwave`
- `POST /api/subscription/webhook/stripe|razorpay`
- `GET|POST /api/whatsapp/webhook/{schoolCode}`

### Web

- `POST /webhook/razorpay|stripe|paystack|flutterwave`
- `POST /subscription/webhook/stripe|razorpay|paystack|flutterwave`
- Addon/subscription payment success/cancel routes under admin web groups
- `GET /payment/status`, `payment.cancel`

Gateway dashboards must continue pointing at these paths on the frozen host. Path inventory is approved; dashboard UI confirmation is an ops checklist item before enabling payment canary (`ops/phase2/PAYMENTS_AND_WEBHOOKS.md`).

## Approval checklist

- [x] API hostname frozen from compiled Flutter `baseUrl`
- [x] WebSocket hostname/port/key frozen from Flutter `reverbUrl`
- [x] Media APP_URL provisionally equals API hostname
- [x] Student-web production rule equals frozen API/socket origins
- [x] Payment/webhook path inventory frozen
- [ ] Live HTTP/DNS probe on operator network (`baseline/probe_origins.sh`) — required before Phase 9
- [ ] Gateway dashboard screenshot/checklist — required before payment domain canary

## Sign-off

| Role | Name | Decision | Date |
| --- | --- | --- | --- |
| Migration Engineer | Cursor agent execution | Approved for engineering + fixture work | 2026-10-03 |
| Tech Lead | UNASSIGNED | Required before Phase 9 | |
| Ops / Payments | UNASSIGNED | Required before payment canary | |
