# Laravel routes manifest summary

Parsed from eSchool SaaS V1.11.0 Admin Panel PHP code.

## Sources

| File | Role |
|------|------|
| `routes/api.php` | Mobile/API contracts (all routes) |
| `routes/web.php` | Public payment/webhook/subscription/callback routes only |
| `app/Providers/RouteServiceProvider.php` | Confirms `Route::prefix('api')->middleware('api')` for `api.php`; `web` middleware for `web.php` |

## API (`laravel_api_routes.json`)

- **Total routes:** 253
- **HTTP methods:** GET=153, POST=100
- **Auth breakdown:** bearer=229, none=23, tracking_token=1
- **Tenant source breakdown:** body=9, none=12, path=2, school-code header=229, tracking=1

### Prefix & middleware model

- Global path prefix: `/api` (RouteServiceProvider).
- Default middleware group: `api`.
- Tenant DB switching for authenticated mobile APIs: `APISwitchDatabase` (reads `school-code` header, validates Sanctum bearer token).
- Often combined with `checkSchoolStatus` (student/teacher/staff) or `checkChild` (parent child-scoped).
- Nested `auth:sanctum` appears only on a small teacher student-result subset (in addition to `APISwitchDatabase`).
- WhatsApp Meta webhook uses `{schoolCode}` **path** param (no bearer).
- Live-tracking WebView session uses `X-Tracking-Token` (auth=`tracking_token`, tenant=`tracking`); deliberately outside `APISwitchDatabase`.
- Login / forgot-password routes are unauthenticated and expect `school_code` in the **body**.

### Major path groups

| Prefix | Audience |
|--------|----------|
| `/api/student/*` | Student app |
| `/api/parent/*` | Parent/guardian app (fees under `/api/parent/fees`) |
| `/api/teacher/*` | Teacher app (+ `/online-classes`) |
| `/api/staff/*` | Staff app (payroll, QR attendance, tasks, leaves) |
| `/api/webhook/*`, `/api/subscription/webhook/*` | Payment provider webhooks |
| `/api/whatsapp/webhook/{schoolCode}` | Meta WhatsApp verify/receive |
| `/api/transportation/*`, `/api/transport/*` | Transportation / live tracking |
| other `/api/*` | Shared settings, chat, leaves, certificates, etc. |

## Web payment/public (`laravel_web_payment_routes.json`)

- **Total routes:** 11
- These are routes **outside** the authenticated `Role` / school-admin middleware stack.
- Includes fee webhooks, subscription webhooks, app payment status/cancel return URLs, and `subscription/cron-job`.
- No public WhatsApp routes exist in `web.php` (WhatsApp webhooks live under `/api/whatsapp/webhook/{schoolCode}`).
- Authenticated admin subscription/addon payment success pages were excluded (session/`Role` protected).

### Routes

- `GET /payment/cancel` → `PaymentController@cancel`
- `GET /payment/status` → `PaymentController@status`
- `GET /subscription/cron-job` → `Controller@cron_job`
- `POST /subscription/webhook/flutterwave` → `SubscriptionWebhookController@flutterwave`
- `POST /subscription/webhook/paystack` → `SubscriptionWebhookController@paystack`
- `POST /subscription/webhook/razorpay` → `SubscriptionWebhookController@razorpay`
- `POST /subscription/webhook/stripe` → `SubscriptionWebhookController@stripe`
- `POST /webhook/flutterwave` → `WebhookController@flutterwave`
- `POST /webhook/paystack` → `WebhookController@paystack`
- `POST /webhook/razorpay` → `WebhookController@razorpay`
- `POST /webhook/stripe` → `WebhookController@stripe`

## Notes for contract tests

- Prefer `/api/...` paths from `laravel_api_routes.json` for Flutter/student-web reconciliation.
- Provider webhooks are registered on **both** `api.php` (`/api/webhook/...`) and `web.php` (`/webhook/...`); treat as parallel entry points.
- `GET /payment/status` is registered twice in `web.php` (identical action); manifest de-duplicates to one record.
- Regenerator: `contract-tests/scripts/parse_laravel_routes.py`.
- Do not modify Laravel source; regenerate these manifests if `routes/*.php` changes.
