# Phase 10 — DNS TTL checklist

Cutover is primarily reverse-proxy upstream change on the **frozen hostname**. Use DNS changes only when the edge/VIP itself must move.

## Before cutover (T−7 to T−2 days)

- [ ] Inventory all public records: API host, admin host, student-web host, media/CDN, WebSocket host
- [ ] Confirm which records are CNAME vs A/AAAA vs load-balancer aliases
- [ ] Lower TTL on records that may flip (recommend **60–300 seconds**)
- [ ] Wait at least one prior TTL period so resolvers pick up the low TTL
- [ ] Document current targets and the rollback targets side-by-side
- [ ] Verify registrar/DNS API access for on-call engineers

## At cutover

- [ ] Prefer proxy upstream flip **without** DNS change when possible
- [ ] If DNS must move: change record → verify dig from multiple resolvers → smoke tests
- [ ] Keep old target warm for rollback

## After stabilization

- [ ] Confirm no split-brain (clients hitting both old and new unintentionally)
- [ ] Raise TTL to steady-state values (e.g. 300–3600s per org policy)
- [ ] Store final record set in ops notes / runbook appendix

## Rollback note

High TTL at cutover time lengthens client pain. If TTL was not lowered, rollback still flips proxy/DNS immediately, but global convergence may take the full prior TTL.
