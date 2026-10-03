# Canary write-ownership matrix

Approved Baseline on 2026-10-03 by Migration Engineer.

All domains start in **Baseline** (Laravel owns everything). Approver must sign the canary state change before a domain leaves Baseline.

| Domain | Routes | Writes | Clients | API read | API write | Admin write | Webhook | Worker/schedule | Approver | Status |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `certificate` | 2 | yes | flutter_staff, flutter_student, student_web | Laravel | Laravel | Laravel | n/a | Laravel | Tech Lead | approved_baseline |
| `certificates` | 1 | no | none | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `change-password` | 1 | yes | flutter_staff, flutter_student, student_web | Laravel | Laravel | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `class-section` | 1 | yes | student_web | Laravel | Laravel | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `classes` | 1 | no | flutter_staff | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `country-codes` | 1 | no | flutter_staff | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `create-transportation-expense` | 1 | yes | flutter_staff | Laravel | Laravel | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `delete` | 1 | yes | flutter_staff, flutter_student, student_web | Laravel | Laravel | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `delete-my-leaves` | 1 | yes | none | Laravel | Laravel | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `diaries` | 1 | no | flutter_staff, flutter_student, student_web | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `driver` | 4 | yes | flutter_staff | Laravel | Laravel | Laravel | n/a | Laravel | Tech Lead + Transport Owner | approved_baseline |
| `fees-due-notification` | 1 | no | none | Laravel | n/a | Laravel | n/a | Laravel | Ops/Payments + Tech Lead | approved_baseline |
| `firebase-config` | 1 | no | none | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `forgot-password` | 1 | yes | flutter_staff, flutter_student | Laravel | Laravel | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `gallery` | 1 | no | flutter_student, student_web | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `get-image` | 1 | no | flutter_staff | Laravel | n/a | Laravel | Laravel | Laravel | Migration Engineer | approved_baseline |
| `get-languages` | 1 | no | flutter_staff, flutter_student, student_web | Laravel | n/a | Laravel | n/a | Laravel | Tech Lead | approved_baseline |
| `get-transportation-expense` | 1 | no | flutter_staff | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `get-vehicle-assignment-status` | 1 | yes | flutter_staff, flutter_student | Laravel | Laravel | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `holidays` | 1 | no | flutter_staff, flutter_student, student_web | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `leave-settings` | 1 | no | flutter_staff, flutter_student | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `leaves` | 2 | yes | flutter_staff | Laravel | Laravel | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `logout` | 1 | yes | flutter_staff, flutter_student | Laravel | Laravel | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `medium` | 1 | no | flutter_staff | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `message` | 3 | yes | flutter_staff, flutter_student, student_web | Laravel | Laravel | Laravel | n/a | Laravel | Tech Lead | approved_baseline |
| `my-leaves` | 1 | no | none | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `notifications` | 1 | no | flutter_staff, flutter_student, student_web | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `parent` | 44 | yes | flutter_student | Laravel | Laravel | Laravel | n/a | Laravel | Ops/Payments + Tech Lead | approved_baseline |
| `payment-confirmation` | 1 | no | flutter_student | Laravel | n/a | Laravel | n/a | Laravel | Ops/Payments + Tech Lead | approved_baseline |
| `payment-transactions` | 1 | no | flutter_student | Laravel | n/a | Laravel | n/a | Laravel | Ops/Payments + Tech Lead | approved_baseline |
| `pickup-points` | 1 | no | flutter_staff, flutter_student | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `profile` | 1 | no | flutter_staff | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `school-details` | 1 | no | flutter_staff, flutter_student | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `school-settings` | 1 | no | flutter_staff, flutter_student, student_web | Laravel | n/a | Laravel | n/a | Laravel | Tech Lead | approved_baseline |
| `semester` | 1 | no | flutter_student, student_web | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `session-years` | 1 | no | flutter_staff, flutter_student, student_web | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `set-languages` | 1 | yes | flutter_staff, flutter_student, student_web | Laravel | Laravel | Laravel | n/a | Laravel | Tech Lead | approved_baseline |
| `settings` | 1 | no | flutter_staff, flutter_student, student_web | Laravel | n/a | Laravel | n/a | Laravel | Tech Lead | approved_baseline |
| `staff` | 48 | yes | flutter_staff | Laravel | Laravel | Laravel | n/a | Laravel | Tech Lead | approved_baseline |
| `staff-leaves-details` | 1 | no | flutter_staff | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `student` | 35 | yes | flutter_student, student_web | Laravel | Laravel | Laravel | n/a | Laravel | Tech Lead | approved_baseline |
| `student-details` | 1 | no | flutter_staff, flutter_student | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `student-exan-result-pdf` | 1 | no | flutter_staff, flutter_student, student_web | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `subscription` | 2 | yes | none | Laravel | Laravel | Laravel | Laravel | Laravel | Ops/Payments + Tech Lead | approved_baseline |
| `system-settings` | 1 | no | student_web | Laravel | n/a | Laravel | n/a | Laravel | Tech Lead | approved_baseline |
| `teacher` | 48 | yes | flutter_staff | Laravel | Laravel | Laravel | n/a | Laravel | Tech Lead | approved_baseline |
| `teachers` | 1 | no | flutter_student, student_web | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `transport` | 11 | yes | flutter_staff, flutter_student, student_web | Laravel | Laravel | Laravel | n/a | Laravel | Tech Lead + Transport Owner | approved_baseline |
| `transportation` | 7 | yes | flutter_staff, flutter_student, student_web | Laravel | Laravel | Laravel | n/a | Laravel | Tech Lead + Transport Owner | approved_baseline |
| `transportation-fees` | 1 | no | flutter_staff, flutter_student | Laravel | n/a | Laravel | n/a | Laravel | Ops/Payments + Tech Lead | approved_baseline |
| `transportation-payments` | 1 | yes | flutter_staff, flutter_student | Laravel | Laravel | Laravel | n/a | Laravel | Tech Lead + Transport Owner | approved_baseline |
| `transportation-requests` | 1 | yes | none | Laravel | Laravel | Laravel | n/a | Laravel | Tech Lead + Transport Owner | approved_baseline |
| `transportation-shifts` | 1 | no | flutter_staff, flutter_student | Laravel | n/a | Laravel | n/a | Laravel | Tech Lead + Transport Owner | approved_baseline |
| `update-profile` | 1 | yes | flutter_staff | Laravel | Laravel | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `users` | 2 | no | flutter_staff, flutter_student, student_web | Laravel | n/a | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `users-by-role` | 1 | yes | flutter_staff | Laravel | Laravel | Laravel | n/a | Laravel | Migration Engineer | approved_baseline |
| `webhook` | 4 | yes | none | Laravel | Laravel | Laravel | Laravel | Laravel | Ops/Payments + Tech Lead | approved_baseline |
| `whatsapp` | 2 | yes | none | Laravel | Laravel | Laravel | Laravel | Laravel | Ops/Payments + Tech Lead | approved_baseline |

## Transfer rule

API, admin, webhook, queue, cache invalidation, and schedule ownership for a domain move as one lifecycle.
Never FastAPI mobile writes + Laravel Blade writes on the same workflow without a reviewed concurrency proof.
