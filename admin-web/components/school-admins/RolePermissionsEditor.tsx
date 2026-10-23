"use client";

import { useEffect, useMemo, useState } from "react";
import { PERMISSION_MODULES, permissionKey, type PermissionAction } from "@/lib/schoolAdminUsers/constants";
import { loadSchoolAdminPermissions, loadSchoolAdminRoles, permissionsFollowRole, updateSchoolAdminRoles } from "@/lib/schoolAdminUsers/api";
import type { SchoolAdminUser } from "@/lib/schoolAdminUsers/types";
import { apiErrorMessage } from "@/lib/api";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";

const ACTIONS: PermissionAction[] = ["read", "write", "manage"];

export function RolePermissionsEditor({ admin }: { admin: SchoolAdminUser }) {
  const [roleKey, setRoleKey] = useState(admin.role_key);
  const [selected, setSelected] = useState<Set<string>>(new Set(admin.permission_keys));
  const [roles, setRoles] = useState<{ key: string; label: string; editable: boolean; permission_keys: string[] }[]>([]);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const readOnly = !admin.can_edit_roles;
  // On the live backend permissions come from the role, so only the role can change.
  const fixedByRole = permissionsFollowRole();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      const [rolesResult, permResult] = await Promise.all([loadSchoolAdminRoles(), loadSchoolAdminPermissions()]);
      if (cancelled) return;
      if (rolesResult.ok) {
        setRoles(
          (rolesResult.data.items || []).map((r) => ({
            key: r.key,
            label: r.label,
            editable: r.editable,
            permission_keys: r.permission_keys,
          })),
        );
      }
      if (permResult.ok) {
        const map: Record<string, string> = {};
        for (const p of permResult.data.items || []) map[p.key] = p.label;
        setLabels(map);
      }
      setLoading(false);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setRoleKey(admin.role_key);
    setSelected(new Set(admin.permission_keys));
  }, [admin]);

  const dirty = useMemo(() => {
    if (roleKey !== admin.role_key) return true;
    const current = [...selected].sort().join(",");
    const original = [...admin.permission_keys].sort().join(",");
    return current !== original;
  }, [admin, roleKey, selected]);

  function onRoleChange(next: string) {
    setRoleKey(next);
    const role = roles.find((r) => r.key === next);
    if (role) setSelected(new Set(role.permission_keys));
  }

  function togglePermission(key: string) {
    if (readOnly || fixedByRole) return;
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function save() {
    setSaving(true);
    setError("");
    setNotice("");
    const result = await updateSchoolAdminRoles(admin.id, {
      role_key: roleKey,
      permission_keys: [...selected],
    });
    setSaving(false);
    setConfirmOpen(false);
    if (!result.ok) {
      setError(apiErrorMessage(result.data, "Unable to save role changes."));
      return;
    }
    setNotice("Roles and permissions updated.");
  }

  if (loading) {
    return <div className="panel-card skeleton" style={{ height: 200 }} />;
  }

  return (
    <section className="panel-card">
      <div className="panel-card-header">
        <h2>Roles &amp; permissions</h2>
      </div>
      {notice ? <div className="alert alert-success">{notice}</div> : null}
      {error ? <div className="alert alert-danger">{error}</div> : null}
      {readOnly ? (
        <div className="alert alert-info">You can view this user&apos;s permissions. Editing is not authorized for this account.</div>
      ) : null}

      <div className="form-field" style={{ maxWidth: 420 }}>
        <label htmlFor="perm-role">Assigned role</label>
        <select id="perm-role" value={roleKey} disabled={readOnly} onChange={(e) => onRoleChange(e.target.value)}>
          {roles.map((role) => (
            <option key={role.key} value={role.key}>
              {role.label}
            </option>
          ))}
        </select>
      </div>

      {fixedByRole && !readOnly ? (
        <p className="field-hint">Permissions come from the assigned role. Choose a different role to change them.</p>
      ) : null}

      <div className="perm-matrix-wrap">
        <table className="data-table perm-matrix">
          <thead>
            <tr>
              <th>Module</th>
              {ACTIONS.map((action) => (
                <th key={action}>{action}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {PERMISSION_MODULES.map((mod) => (
              <tr key={mod.key}>
                <td>{mod.label}</td>
                {ACTIONS.map((action) => {
                  const key = permissionKey(mod.key, action);
                  const checked = selected.has(key);
                  const label = labels[key] || key;
                  return (
                    <td key={key}>
                      <label className="perm-check">
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={readOnly || fixedByRole}
                          aria-label={label}
                          onChange={() => togglePermission(key)}
                        />
                      </label>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!readOnly ? (
        <div className="resource-actions">
          <button className="btn-pill btn-pill-green" type="button" disabled={!dirty || saving} onClick={() => setConfirmOpen(true)}>
            Save permissions
          </button>
        </div>
      ) : null}

      {confirmOpen ? (
        <ConfirmDialog
          title="Save permission changes"
          body={`Update role and permissions for ${admin.first_name} ${admin.last_name}? The backend will enforce access regardless of UI settings.`}
          confirmLabel="Save"
          pending={saving}
          onCancel={() => setConfirmOpen(false)}
          onConfirm={() => void save()}
        />
      ) : null}
    </section>
  );
}
