# QA round 3: fee wording, Request demo, Refund policy, installment labels

Branch `qa/fees-demo-refund`, 12 Nov 2026, built on main (`5fdc23f`, Nitish's branch commit). No backend changes.

## Results

- **Tests:** 22 files, 183 / 183 (10 new). Type check and production build pass with 0 warnings.
- **Walkthrough** (headless Chrome against a local production build and fake API; the fake API answers `POST /public/demo-requests` with 404, like the live backend):
  - **27 / 27 checks** at 1366 px and 375 px, signed out and signed in, with **no console errors**
  - screenshots in [`qa-screenshots/round3/`](qa-screenshots/round3/), results in `round3/results.json`

## Issue 1: Conflicting fee assignment instructions (P2): fixed

**The rule, confirmed in Nitish's backend** (`school_academic_mgmt.py`):
- A fee assignment row is only created by the explicit assign route. Nothing assigns a class's fee structure automatically, not even on admission.
- Balances, outstanding fees and collection all come from assignments.
- A concession is a per-student, per-structure discount (percent or fixed) that lowers that structure's payable amount.

**One explanation, in `lib/ops/feeCopy.ts`, used everywhere on the page:**

| Place | Now says |
| --- | --- |
| Page text | A student owes a fee structure only after it's assigned to them here. Assign each class's standard fee structure to its students, assign optional fees (like transport) to the students who take them, and record concessions to lower what a student owes. |
| Section / button | "Fee assignments" / "Assign fee structure" |
| Empty table | No fee structures are assigned yet. Students owe nothing until a fee structure is assigned to them. |
| Dialog | **Assign a fee structure to a student**: The student will owe this structure's installments, less any concession. Use it for the class's standard fees and for optional fees such as transport. |

The sample-data mode, where class fees do apply automatically, keeps its own matching wording. Assigning and removing work as before.

**Business decision still open:** if class structures should apply to every student automatically, Nitish needs to add automatic assignment on admission, or a "assign to whole class" route. The wording would then change in one place.

## Issue 2: Request Demo went to login (P2): fixed, waiting on one backend route

- "Request demo" (hero) and "Book a demo" (pricing) now open **`/request-demo`**.
  - It's a public page, open whether or not you're signed in, with no redirect to the dashboard (middleware test plus walkthrough).
- The form asks for name, school name, email and phone (required), plus city, number of students and what they'd like to see, with field validation.
- The form submits to **`POST /api/v1/public/demo-requests`**. That route **doesn't exist yet**: the backend has only per-school contact inquiries, which land in one school's inbox. Until it exists:
  - the form says plainly that the request **wasn't sent**;
  - it offers a pre-filled email to `CONTACT.email` instead;
  - it never shows a false success. Once the route exists, the form works with no frontend change.
- **For Nitish:** `POST /public/demo-requests` should:
  - accept `{name, school_name, email, phone, city?, students?, message?}`;
  - return `201 {id}` on success and `422 {detail}` on validation errors;
  - be rate-limited, and store the request for the Super Admin, ideally with a list route.
- **To confirm:** `CONTACT.email` (`hello@schoolsarthi.app`) and the phone/address in `lib/marketing/content.ts` are placeholders. Please supply the real contact details.
- **Also noticed (not in this ticket):** the homepage Contact form doesn't send anything. It shows "ready to send when a contact API is connected". It could use the same new route.

## Issue 3: Refund Policy link (P2): fixed; wording pending

- The footer "Refund Policy" now opens the public **`/refund-policy`** page, which has the same layout as Terms and Privacy.
- **No refund terms were invented.** The page says the policy will be published soon and to contact us. Once the approved wording is supplied, put it in `lib/marketing/refund.ts` (`REFUND_POLICY.sections`) and set `REFUND_POLICY_PUBLISHED = true`.

## Issue 4: Two-installment label (P3): fixed

- **Cause:** splitting kept each row's existing name, so the default "Full payment" survived a 2-part split. Labels are frontend-only; the backend stores whatever name is sent.
- **Fix:**
  - presets are named "Full payment" (one payment) or "Installment 1…N" (2, 3, 4 parts and 12 monthly), and re-split as needed;
  - names the admin typed (e.g. "Term 1") are kept;
  - "+ Add installment" also renames a lone "Full payment" to "Installment 1".
- **Amounts are unchanged** (`splitEvenly`). ₹1,200 in 2 parts gives Installment 1 and Installment 2 at ₹600.00 each, planned ₹1,200.00 of ₹1,200.00. Checked for one payment and 2, 3, 4 and 12 parts.

## Deploy

Not deployed yet. Pushing to main deploys to Netlify (https://eschool-saas.netlify.app), and that waits for your approval.
