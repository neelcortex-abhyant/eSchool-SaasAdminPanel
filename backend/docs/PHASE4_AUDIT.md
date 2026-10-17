"""Historical snapshot, written before the v1 plan API existed.

Do not use this file as the current contract. Plans are now implemented.
See docs/SUBSCRIPTION_RENEWAL_API.md. The findings below are what this
audit recorded at the time. They are not a claim about the code today.

Phase 4 audit (plans / packages).

Existing Package model (`packages` table):
  id, name, description, status, deleted_at, created_at, updated_at

Existing routes:
  GET /api/admin/packages — list only (legacy cookie auth)
  Dashboard counts packages / packages_active
  No v1 Super Admin package CRUD

Catalog names only (no models / no migrations in this repo):
  features, package_features, subscriptions, addons,
  addon_subscriptions, subscription_bills, subscription_features

Missing for Phase 4:
  - /api/v1/super-admin/plans CRUD + status
  - pricing + student/staff limit columns on packages

Reuse: Package table/model, require_super_admin, soft-delete pattern.
Do NOT create a separate plans table.
Do NOT implement subscriptions/billing/addons (later phases).

Migration 0006: additive columns on packages only.

Current state, after later implementation:
  POST/GET/PATCH /api/v1/super-admin/plans and PATCH .../status exist.
  They use the packages table. Migration 20261007_0006 is in the repository.
  This snapshot's "missing" list was the gap at audit time, not the live API.
"""
