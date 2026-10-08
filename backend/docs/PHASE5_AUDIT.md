"""Phase 5 audit: Subscriptions + Subscription Bills.

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
"""
