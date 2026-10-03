# Phase 4 status — Authentication and middleware

## Done

- Multipart logins for student/parent/teacher/staff
- Login resources expanded toward Laravel `UserDataResource` (student + guardian children + staff roles/school)
- Logout variants with fcm_id / device_id / web_fcm
- `$2y$` bcrypt + Sanctum tokens
- Golden fixtures captured for all five roles + logout + cross-tenant denial
- Unit tests: 7 passed

## Remaining for full parity

- Nested `teacher` / `staff` salary graphs from Laravel eager loads
- Exact `trans()` localized strings vs English fallbacks
- Forgot-password / change-password flows
- Full FCM token-table service parity

## Gate

**Auth bootstrap engineering gate: PASS** against synthetic fixtures.  
Re-capture against production-shaped dumps when available and diff nested salary graphs.
