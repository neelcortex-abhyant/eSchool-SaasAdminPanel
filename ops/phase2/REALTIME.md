# Realtime (Reverb / Pusher protocol) — Phase 2 operational design

## Decision

**Keep Laravel Reverb as the WebSocket server** through canary and initial cutover. FastAPI **publishes** events into Reverb (or the same Redis broadcasting backend Reverb consumes). Replacing Reverb requires an independently approved client release — Flutter hardcodes `reverbUrl` / app key in `constants.dart`.

Frozen socket origin (draft):  
`ws://stage-eschool-saas.wrteam.net:9090/app/e2mhe9gu4tb2x2vkncxa`  
(Confirm production values in [baseline/FROZEN_ORIGINS.md](../../baseline/FROZEN_ORIGINS.md).)

---

## FastAPI publish path

Preferred order:

1. **HTTP to Reverb / Pusher-compatible HTTP API** using the same `REVERB_APP_ID`, `REVERB_APP_KEY`, `REVERB_APP_SECRET`, host, port, and scheme as Laravel broadcasting config.
2. **Redis pub/sub** into the channel layout Laravel’s broadcaster already uses (only if binary-compatible with current Reverb Redis config — verify in staging before production).

Do **not** open a second WebSocket host for clients. Clients continue to connect to the frozen `/app/{key}` endpoint.

Publish from FastAPI only when the domain’s ownership row says FastAPI owns writes that emit the event (chat, provisioning progress, system update progress, academy wizard).

---

## Exact Pusher protocol requirements (client-visible)

Clients (Flutter + student-web) speak the Pusher protocol against Reverb. FastAPI must not change these behaviors:

| Requirement | Detail |
| --- | --- |
| Connect path | `/app/{key}` with frozen app key |
| Connection | Server sends `pusher:connection_established` with `socket_id` |
| Subscribe | Client subscribes to public channels (current product uses public `user.{id}` style channels — preserve auth rules as Laravel `routes/channels.php` / broadcasting config) |
| Ping / pong | `pusher:ping` / `pusher:pong`; accept string **or** object data forms clients send |
| Chat channel | `user.{userId}` |
| Chat event name | **`NewMessage`** (must match Laravel `broadcastAs` / ApiController `event: 'NewMessage'`) |
| Chat payload | `{ "from", "to", "message" }` as today (`MessageSent::broadcastWith`) |
| Event naming | Preserve Laravel convention: custom event names without breaking clients that listen for `NewMessage` / `App\\Events\\NewMessage` compatibility as currently working in production |
| Provisioning | Channel `school.{schoolId}`, event `school.provision.progress`, payload fields: `school_id`, `school_name`, `step`, `step_label`, `progress`, `status` (`installing`\|`completed`\|`failed`), `message` |
| System update | Preserve `SystemUpdateProgressEvent` channel + `broadcastAs` + payload |
| Academy wizard | Preserve `AcademySetupProgressUpdated` channel + event + payload |

Any deviation that requires a Flutter rebuild is out of scope.

---

## Ownership and dual-publish

| State | Chat / progress publisher |
| --- | --- |
| Baseline | Laravel only |
| Read canary | Laravel only |
| Domain write canary (chat / provision) | **FastAPI only** for that domain’s events |
| Forbidden | Both stacks broadcasting the same message id / progress step |

---

## Security notes

- Reverb `allowed_origins` is currently `*` in archive config — tighten in production when feasible without breaking mobile WebViews; document any change.
- Do not expose `REVERB_APP_SECRET` to browsers; FastAPI server-side only.
- Private/presence channels: if Laravel enables auth endpoints later, FastAPI must serve the same auth route shapes — inventory before changing.

---

## Test plan (protocol)

1. Connect with a Pusher client library pointed at frozen origin; assert `pusher:connection_established`.
2. Subscribe `user.{id}`; send chat via FastAPI; assert event name + payload golden match.
3. Ping/pong both payload shapes.
4. Run provisioning job; assert progress channel monotonic `progress` and terminal `completed`/`failed`.
5. Rollback publisher to Laravel; no duplicate events for one message.

---

## Acceptance pointers

Phase 7 gate in the migration plan: chat, tracking (HTTP), and progress channels pass exact protocol tests before schedule ownership transfer completes.
