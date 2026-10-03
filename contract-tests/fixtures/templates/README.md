# Fixture templates (Phase 1)

These are **request/response schemas** to capture against Laravel once sanitized MySQL dumps exist. They are not golden bodies yet.

## Capture rules

1. Hit live/staging Laravel (or local with dumps) using exact client encoding.
2. Sanitize secrets/PII; keep IDs, types, nullability, nested graphs, filenames.
3. Store under `fixtures/golden/<role>/<endpoint>/`.
4. Diff FastAPI against these files; no silent field drops.

## Priority pack (auth + bootstrap)

| ID | Role | Endpoint | Encoding | Why |
| --- | --- | --- | --- | --- |
| A1 | student | `POST /api/student/login` | multipart | Complete student resource |
| A2 | parent | `POST /api/parent/login` | multipart | Parent + complete children |
| A3 | teacher | `POST /api/teacher/login` | multipart | Teacher graph |
| A4 | school-admin | `POST /api/teacher/login` | multipart | Same path, school-admin role graph |
| A5 | driver | `POST /api/teacher/login` | multipart | Driver graph |
| L1 | any | `POST /api/logout` + `device_id` | multipart | FCM cleanup by device |
| L2 | any | `POST /api/logout` + `fcm_id` | multipart | FCM cleanup by token |
| L3 | student-web | `POST /api/logout` + `web_fcm` | multipart | Web push cleanup |
| L4 | any | `POST /api/logout` no device | multipart | All-device / legacy `users.fcm_id` clear |
| B1 | staff | `GET /api/staff/features-permission` | query | Staff UI bootstrap |
| B2 | staff | `GET /api/school-settings` | query | School settings bootstrap |
| B3 | all | `GET /api/get-languages` + `POST /api/set-languages` | query/multipart | Localized labels |
| M1 | all | login failure / denial messages | multipart | Exact `trans()` strings |

See individual JSON schemas in this folder.
