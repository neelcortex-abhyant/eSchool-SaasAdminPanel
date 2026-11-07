# School ERP — Frontend Handoff (Nitish / Admin Web)

**Backend will not modify `admin-web/`.** These items need Admin Web changes.

## BUG-01 — Registration domain shows `.localhost`

**Backend verify (2026-11-05):** `POST /api/v1/schools/register` accepts `domain` / `domain_type` and persists on `schools` (`school_registration.py` + school service). Response is `{school_id, status, message}` — preview hostname is FE-built.

**Cause:** `NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN` defaults to `localhost` in `admin-web/lib/domains/core.ts`.

**Fix:**

1. Set Netlify env `NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN` to the real root (e.g. `eschool-saas.netlify.app` or custom apex).
2. Confirm registration preview uses that env, not a hard-coded localhost suffix.
3. Backend already stores `schools.domain` / `domain_type` via registration APIs — no backend URL builder change required for preview.

## BUG-02 — Terms / Privacy go to Contact

**Backend verify (2026-11-05):** Content slugs `privacy_policy` / `terms_condition` are allowed in `school_settings_cms` and served via `GET/PUT /school-admin/content/{slug}`.

**Cause:** `admin-web/components/marketing/SiteFooter.tsx` uses `href="#contact"` for Privacy and Terms.

**Fix:** Point to real routes/pages that load content slugs `privacy_policy` and `terms_condition` (school content API `/school-admin/content/{slug}` or public content routes). Backend CMS tables/APIs already support these slugs.

## BUG-03 — Class/section validation stuck after valid select

**Backend verify (2026-11-05):** Student create returns 422 with clear `class_section_id` messages when missing/invalid (`school_people.create_student` / `_assert_active_class_section`).

**Cause:** `admin-web/components/people/StudentForm.tsx` keeps `fieldErrors.class_section_id` / class errors after the user selects valid values.

**Fix:** Clear those field errors in `onChange` for class and section (and session) controls before submit.

## Branch UI contract (new backend)

| Item | Contract |
|---|---|
| List branches | `GET /api/v1/school-admin/branches` |
| Create | `POST /api/v1/school-admin/branches` `{name, code?, address?}` |
| Get / patch | `GET|PATCH /api/v1/school-admin/branches/{id}` |
| Assign admins | `PUT /api/v1/school-admin/branches/{id}/admins` `{user_ids: uuid[]}` |
| Active branch | Header `X-Branch-Id: <int>` on operational school-admin calls |
| Me payload | `GET /school-admin/me` additive: `branches[]`, `default_branch_id`, `active_branch_id` (when header sent) |

School Admin may omit header → server uses default branch. Branch Admin must send an assigned branch id.

## Fees copy

Align UI text with reality: fee payments **are** persisted via `/fee-payments` / collect APIs when authorized — remove any “not stored” placeholder wording.
