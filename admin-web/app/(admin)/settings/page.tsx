export default function SettingsPage() {
  return (
    <div>
      <h1 className="h3 mb-3">Settings</h1>
      <p className="text-muted">
        Auth is on <code>/api/v1</code>. School modules labeled “legacy” still call{" "}
        <code>/api/admin</code> and need the MySQL-backed admin API.
      </p>
    </div>
  );
}
