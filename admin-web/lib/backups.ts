/**
 * Platform backups (super admin): GET/POST /super-admin/backups and
 * POST /super-admin/backups/{id}/restore {confirmation: "RESTORE"}. The server says what each
 * backup really is: today it writes a metadata record only ("metadata_only"), and a restore only
 * records the request. Its messages are shown as they come, so nobody mistakes them for a dump.
 */
export type Backup = {
  id: number;
  status: string;
  size_bytes: number | null;
  checksum: string | null;
  error_message: string | null;
  expires_at: string | null;
  created_at: string | null;
};

const STATUS: Record<string, { label: string; tone: string }> = {
  pending: { label: "In progress", tone: "pending" },
  metadata_only: { label: "Record only, not a database copy", tone: "pending" },
  completed: { label: "Complete", tone: "paid" },
  failed: { label: "Failed", tone: "failed" },
  restored_requested: { label: "Restore requested", tone: "pending" },
};

export function backupStatus(status: string): { label: string; tone: string } {
  return STATUS[status] ?? { label: status || "Unknown", tone: "pending" };
}
