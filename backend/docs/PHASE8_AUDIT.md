"""Phase 8 audit: Settings + Audit Logs + Notifications.

Live Neon (alembic 20261007_0008):
  system_settings EXISTS (id, name, data, type) — empty; used by legacy web_maintenance
  school_settings DOES NOT EXIST (catalog only)
  notifications DOES NOT EXIST — mobile GET /notifications returns []
  audit_logs DOES NOT EXIST
  announcements EXISTS (school-scoped; not platform SA notifications)

Reuse:
  SystemSetting for platform settings (no duplicate settings table)
  AuthContext.user for actor identity
  require_super_admin

Missing:
  audit_logs table + GET API + write helper
  notifications table + SA admin APIs
  v1 Super Admin settings GET/PATCH

Migration 0009: create audit_logs + notifications (additive).
No email/SMS/push providers in Phase 8.
"""
