# Phase 1 status — exhaustive contract lock

## Flutter source root

`/Users/apple/eSchool-SaasAppCode/`

## Done

- Reconciled manifests + critical mismatch decisions
- Ownership matrix Baseline approved with named approvers
- Auth/bootstrap golden fixtures captured under `contract-tests/fixtures/golden/`
- Sanitization rules applied (tokens/FCM redacted)

## Gate

| Item | Status |
| --- | --- |
| Reachable client calls reconciled | Pass (orphans decided) |
| Encoding recorded | Pass |
| Ownership matrix approved Baseline | Pass |
| Auth/bootstrap golden fixtures | Pass (synthetic dataset) |
| Full golden suite every reachable route | In progress — expand beyond auth pack |
| Public-origin freeze | Pass (engineering); live probe before Phase 9 |

## Next

Replace stubs domain-by-domain against golden fixtures, starting with student/parent reads.
