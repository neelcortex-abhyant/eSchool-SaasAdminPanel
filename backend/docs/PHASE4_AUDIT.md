"""Phase 4 audit (plans / packages).

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
"""
