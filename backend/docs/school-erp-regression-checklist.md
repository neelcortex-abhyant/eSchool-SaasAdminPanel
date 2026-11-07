# School ERP — Proposed Regression Checklist

Derived from the School ERP requirements document.  
**Original 29 test cases:** BLOCKED (not in repository — do not claim passed).

| ID | Journey / check | Layer | Status |
|---|---|---|---|
| R-01 | School registration API creates school + admin | Backend | Covered (existing registration tests) |
| R-02 | Login valid / invalid credentials | Backend | Covered (existing auth tests) |
| R-03 | Duplicate email handling on registration | Backend | Covered (existing) |
| R-04 | Create Branch 2 under same school_id | Backend | Code + offline; DB E2E pending |
| R-05 | Branch 1 unchanged after Branch 2 create | Backend | Code contract; DB E2E pending |
| R-06 | Assign branch admin via v1_user_branch_access | Backend | Service + route; DB E2E pending |
| R-07 | Branch admin denied other branch (IDOR) | Backend | Offline unit PASS |
| R-08 | School admin lists both branches | Backend | Route registered |
| R-09 | Student create scoped to X-Branch-Id | Backend | Wired; DB E2E pending |
| R-10 | Cross-branch student lookup rejected | Backend | Offline assert_same_branch + owned filter |
| R-11 | Fee structure + assignment + payment same branch | Backend | Wired; DB E2E pending |
| R-12 | Duplicate payment protection | Backend | Existing idempotency reused |
| R-13 | Attendance / exam / homework branch filter | Backend | Wired; DB E2E pending |
| R-14 | Consolidated report = sum of allowed branches | Backend | Wired reports; DB E2E pending |
| R-15 | Default branch delete rejected | Backend | Service raises 422 |
| R-16 | Disabled branch blocks new writes | Backend | resolve_branch_context 403 |
| R-17 | BUG-01 domain preview | Admin Web | Handoff |
| R-18 | BUG-02 privacy/terms links | Admin Web | Handoff |
| R-19 | BUG-03 class/section validation clear | Admin Web | Handoff |
| R-20 | Forgot-password / reset email | Backend+env | Existing + env blockers doc |
| R-29-ORIG | Original 29 QA cases | QA | **BLOCKED** |
