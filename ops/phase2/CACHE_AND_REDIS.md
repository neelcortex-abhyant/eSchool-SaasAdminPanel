# Cache and Redis — Phase 2 operational design

## Decision

During canary and cutover, **Laravel and FastAPI share one Redis**. Do not stand up a second cache cluster until after Laravel is archived.

| Use | Redis DB / prefix | Shared? |
| --- | --- | --- |
| Laravel cache | Existing `CACHE_PREFIX` / DB index from `.env` | Yes — FastAPI must use same |
| Laravel queues | Existing queue connection | Laravel-owned until job transfer |
| ARQ / FastAPI queues | Prefix `fastapi:arq:` (or Celery `fastapi-celery`) | Separate keys; same Redis |
| Distributed locks | Prefix `lock:` | Shared semantics; one owner per lock name |
| Reverb / broadcasting | Existing Reverb Redis config | Keep; FastAPI publishes via HTTP/Redis to Reverb |
| Sessions (admin) | Laravel session store today; FastAPI admin cookies later | Do not collide prefixes |

**Do not change `APP_KEY`.** Transportation tracking links and any signed payloads depend on it.

---

## Key namespaces to preserve

Exact Laravel cache key strings from `config/constants.php` + `CachingService` + tracking:

### System-level (no school suffix)

| Logical | Key string | TTL (Laravel default) | Invalidate when |
| --- | --- | --- | --- |
| System settings | `systemSettings` | 3600s | Any system setting write |
| Languages | `languages` | 3600s | Language CRUD |
| Features (system) | `features` | 3600s | Feature/package changes |
| School custom form fields | `schoolCustomFormFields` | 3600s | Form field admin changes |
| Guidances | `guidances` | 3600s | Guidance CRUD |
| FAQs | `faqs` | 3600s | FAQ CRUD |

### School-level (`{base}_{schoolId}`)

`CachingService::schoolLevelCaching` appends `_{schoolId}`:

| Logical | Base key | Example | Invalidate when |
| --- | --- | --- | --- |
| School settings | `schoolSettings` | `schoolSettings_12` | School settings save (incl. `time_zone`, payment keys metadata) |
| Session year | `sessionYear` | `sessionYear_12` | Session year mutations |
| Semester | `semester` | `semester_12` | Semester mutations |
| Features (school) | `features` | `features_12` | Feature assignment / subscription |
| Leave master | `leaveMaster` | `leaveMaster_12` | Leave master changes |
| All session years | `allSessionYears` | `allSessionYears_12` | Session year list changes |
| Semesters by session year | `getSemestersBySessionYear` | + school suffix | Semester/session linkage |

### Request/process memo keys (also used as cache in places)

| Key pattern | Notes |
| --- | --- |
| `defaultSessionYear_{schoolId\|null}` | Default session year |
| `defaultSemesterData_{schoolId\|null}` | Default semester |

FastAPI may keep an in-process request cache, but **cross-request** values must hit Redis with the same key strings so Blade and API stay coherent during mixed ownership.

### Transportation tracking (must stay byte-compatible)

| Key pattern | Purpose |
| --- | --- |
| `transportation:tracking-link:{tokenId}` | Active link record |
| `transportation:school:{schoolId}:tracking-link:user:{userId}:trip:{tripId\|none}` | Reuse last link |
| `transportation:school:{schoolId}:tracking-link:trip:{tripId}` | Trip index for revoke |
| `transportation:school:{schoolId}:tracking-link:issuer:{userId}` | Logout revoke index |

TTL parity: `TrackingLinkService::TTL_MINUTES = 120` (+ after-trip grace). Same `APP_KEY`, signature, expiry, revocation, and rate limits as Laravel.

### WhatsApp / misc

Preserve any existing WhatsApp template cache keys (Laravel uses `Cache::remember` with ~1800s). Inventory exact strings during Phase 3 implementation from `WhatsAppService` before canarying WhatsApp.

### FastAPI-only prefixes (never used by Laravel)

| Prefix | Purpose |
| --- | --- |
| `fastapi:arq:` | Job queue |
| `fastapi:job:done:` | Idempotency markers |
| `arq:dlq` / `fastapi:dlq:` | Dead-letter |
| `lock:` | Shared locks (document every new lock in QUEUE_AND_CRON) |
| `fastapi:ratelimit:` | FastAPI rate limits if not using Laravel throttle keys |

---

## Invalidation rules

1. **Writer owns invalidation.** Only the domain owner (matrix) may `Cache::forget` / Redis `DEL` for that domain’s keys.
2. **Read canary:** FastAPI may read shared cache; must not warm with divergent shapes. If shadow mode, do not write cache.
3. **After school settings write:** forget `schoolSettings_{id}` and any derived keys (`defaultSessionYear_*` if session defaults changed).
4. **After system settings write:** forget `systemSettings` (and languages/features if those tables changed).
5. **Tracking revoke:** same delete patterns as Laravel on trip end / logout.
6. **Never flush DB 0** in production to “fix” canary issues — selective key delete only.
7. **Serialization:** Prefer JSON-compatible structures FastAPI and Laravel both understand. If Laravel stores PHP-serialized values for a key, FastAPI must either use Laravel’s serializer bridge or treat that key as Laravel-only until the domain fully transfers. Priority keys to verify in Phase 3: `systemSettings`, `schoolSettings_*`, tracking-link payloads.

---

## Canary Redis checklist

- [ ] Same host/port/password/DB index as Laravel `REDIS_*`
- [ ] Same cache key prefix as Laravel (`CACHE_PREFIX` if set)
- [ ] `APP_KEY` identical for signed tracking URLs
- [ ] Monitoring: memory, evicted_keys, connected_clients, keyspace hits
- [ ] Alert if unexpected `FLUSH*` commands appear in slowlog
- [ ] Document maxmemory-policy (prefer `noeviction` or `volatile-lru` only if TTLs cover all critical keys — tracking links must not be randomly evicted; use TTL keys)

---

## Acceptance pointers

Shared Redis read/write parity tests and tracking-link round-trip across Laravel issue → FastAPI validate (and reverse) before transport domain write canary.
