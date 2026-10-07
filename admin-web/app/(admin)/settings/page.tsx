import { PageHeading } from "@/components/dashboard/StatCard";
import { IconSettings } from "@/lib/icons";

export default function SettingsPage() {
  return (
    <div>
      <PageHeading
        title="Settings"
        description="Account and platform preferences"
        icon={<IconSettings width={20} height={20} />}
      />

      <div className="panel-card" style={{ maxWidth: 720 }}>
        <p className="muted" style={{ marginTop: 0 }}>
          Authentication uses <code className="mono">/api/v1</code> Bearer tokens. School
          modules that call <code className="mono">/api/admin</code> still need a tenant
          session before list data loads.
        </p>
        <ul className="muted" style={{ paddingLeft: 18, marginBottom: 0 }}>
          <li>Profile and password screens can be expanded here</li>
          <li>Notification and language preferences belong in this area</li>
          <li>School-code multi-tenant login remains a separate backend track</li>
        </ul>
      </div>
    </div>
  );
}
