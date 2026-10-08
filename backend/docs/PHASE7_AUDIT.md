"""Phase 7 audit: Super Admin Dashboard + Reports.

Existing:
  GET /api/v1/super-admin/dashboard → schools, schools_active, packages,
  packages_active, super_admins (dashboard_service.platform_dashboard)
  Legacy GET /api/admin/dashboard → school-scoped student/class counts
  admin_data.count / rows / scoped helpers

Live Neon tables available for metrics:
  schools, packages, subscriptions, subscription_bills, addons,
  addon_subscriptions, students, users, v1_users, fees

NOT available (Phase 9 / later):
  payment_transactions, payment gateways, real collected revenue

Safe metrics to implement:
  - schools total / active (status=1) / inactive (status=0)
  - schools deactivated (status=0 and installed=0)
  - students (students table platform-wide)
  - v1 school_admins / v1 users
  - subscriptions by status (active/expired/cancelled/inactive)
  - plans (=packages) total / active
  - addons total / active; active addon assignments
  - subscription_bills counts + amount sums by status (bill records, NOT gateway revenue)

Reports (filterable lists/summaries from same tables):
  schools, subscriptions, bills

No new tables / no destructive migrations.
"""
