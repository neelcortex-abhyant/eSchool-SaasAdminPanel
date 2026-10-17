"""Historical snapshot, written when subscriptions and bills were not in the schema.

Do not use this file as the current contract. Those tables and the v1
routes were added later. See docs/SUBSCRIPTION_RENEWAL_API.md. The findings
below, including the live-schema check at alembic 20261007_0006, are what
this audit recorded at the time.

Phase 5 audit: Subscriptions + Subscription Bills.

Live Neon schema check (alembic 20261007_0006):
  - packages EXISTS (Phase 4 columns present)
  - subscriptions DOES NOT EXIST
  - subscription_bills DOES NOT EXIST
  - features / package_features / subscription_features / addons DO NOT EXIST

Catalog (`app/models/catalog.py`) lists those names for Laravel import mapping only —
they are NOT models and NOT migrated DDL in this backend.

Existing code:
  - Package / School models (reuse FKs)
  - GET /api/admin/packages (legacy list)
  - /api/v1/super-admin/plans (Phase 4)
  - Stub webhooks only: /subscription/webhook/{razorpay,stripe}
  - No subscription service or v1 subscription routes

Missing (Phase 5):
  - subscriptions table + model
  - subscription_bills table + model
  - Super Admin CRUD under /api/v1/super-admin/...
  - School/package validation, status lifecycle, bill scoping

Out of scope: addons, payment gateways, revenue, features linking (Phase 6+).

Migration 0007: create subscriptions + subscription_bills (additive).

Current state, after later implementation:
  Per-school subscription and bill routes exist under
  /api/v1/super-admin/schools/{school_id}/subscriptions.
  Migration 20261007_0007 is in the repository.
  Renewal history, expiry, and the platform list were added after this snapshot.
  This snapshot's "missing" list was the gap at audit time, not the live API.
"""
