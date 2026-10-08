"""Phase 6 audit: Add-ons.

Live Neon (alembic 20261007_0007):
  - addons DOES NOT EXIST
  - addon_subscriptions DOES NOT EXIST
  - packages / subscriptions / subscription_bills EXIST
  - features / package_features DO NOT EXIST

catalog.py lists `addons` and `addon_subscriptions` for Laravel import mapping only —
no models, routes, or services exist in this backend.

Reuse: School, Package, Subscription, require_super_admin, plan/subscription patterns.
Missing: addon catalog CRUD + school assignment (addon_subscriptions).

Migration 0008: create addons + addon_subscriptions (additive).
Out of scope: payment gateways, revenue, notifications, features linking.
"""
