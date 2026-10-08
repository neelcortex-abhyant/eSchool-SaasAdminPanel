"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { PageHeading } from "@/components/dashboard/StatCard";
import { IconSettings } from "@/lib/icons";

type Profile = {
  id?: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  mobile?: string | null;
  role?: string;
  detail?: string;
  message?: string;
};

export default function SettingsPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [mobile, setMobile] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const result = await api<Profile>("/users/me");
      if (cancelled) return;
      if (!result.ok) {
        setError(apiErrorMessage(result.data, "Unable to load your profile."));
        setLoading(false);
        return;
      }
      setProfile(result.data);
      setFirstName(result.data.first_name || "");
      setLastName(result.data.last_name || "");
      setMobile(result.data.mobile || "");
      setLoading(false);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setNotice("");
    if (!firstName.trim() || !lastName.trim()) {
      setError("Enter first and last name.");
      return;
    }
    setSaving(true);
    setError("");
    const result = await api<Profile>("/users/me", {
      method: "PATCH",
      body: JSON.stringify({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        mobile: mobile.trim() || null,
      }),
    });
    setSaving(false);
    if (!result.ok) {
      setError(apiErrorMessage(result.data, "Unable to update your profile."));
      return;
    }
    setProfile(result.data);
    setNotice("Profile updated.");
  }

  return (
    <div>
      <PageHeading
        title="Settings"
        description="Account profile from /api/v1/users/me"
        icon={<IconSettings width={20} height={20} />}
      />

      {loading ? (
        <div className="panel-card" style={{ maxWidth: 720 }}>
          <div className="skeleton" style={{ height: 18, width: "40%", marginBottom: 12 }} />
          <div className="skeleton" style={{ height: 120 }} />
        </div>
      ) : (
        <form className="panel-card resource-form" style={{ maxWidth: 720 }} onSubmit={onSubmit}>
          {error ? <div className="alert alert-danger">{error}</div> : null}
          {notice ? <div className="alert alert-info">{notice}</div> : null}
          <div className="resource-fields">
            <div className="form-field">
              <label htmlFor="profile-first">First name *</label>
              <input id="profile-first" value={firstName} onChange={(e) => setFirstName(e.target.value)} required />
            </div>
            <div className="form-field">
              <label htmlFor="profile-last">Last name *</label>
              <input id="profile-last" value={lastName} onChange={(e) => setLastName(e.target.value)} required />
            </div>
            <div className="form-field">
              <label htmlFor="profile-mobile">Mobile</label>
              <input id="profile-mobile" value={mobile} onChange={(e) => setMobile(e.target.value)} />
            </div>
            <div className="form-field">
              <label htmlFor="profile-email">Email</label>
              <input id="profile-email" value={profile?.email || ""} readOnly />
            </div>
          </div>
          <div className="resource-actions">
            <button className="btn-pill btn-pill-green" type="submit" disabled={saving}>
              {saving ? "Saving…" : "Update profile"}
            </button>
          </div>
        </form>
      )}
      {profile?.role === "super_admin" ? <PlatformSettings /> : null}
    </div>
  );
}

const PLATFORM_KEYS = [
  "app_name",
  "support_email",
  "support_phone",
  "currency",
  "timezone",
  "web_maintenance",
  "frontend_url",
  "default_language",
  "tagline",
] as const;

type SettingValue = { value?: string | null; secret?: boolean; configured?: boolean };

function PlatformSettings() {
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const result = await api<{ settings?: Record<string, SettingValue> }>("/super-admin/settings");
      if (cancelled) return;
      if (!result.ok) {
        setError(
          result.status === 403
            ? "This account cannot edit platform settings. Sign in with a super admin account."
            : apiErrorMessage(result.data, "Unable to load platform settings."),
        );
        setLoading(false);
        return;
      }
      const next: Record<string, string> = {};
      PLATFORM_KEYS.forEach((key) => {
        next[key] = result.data.settings?.[key]?.value || "";
      });
      setValues(next);
      setLoading(false);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const settings: Record<string, string> = {};
    PLATFORM_KEYS.forEach((key) => {
      settings[key] = values[key] ?? "";
    });
    setSaving(true);
    setError("");
    setNotice("");
    const result = await api("/super-admin/settings", {
      method: "PATCH",
      body: JSON.stringify({ settings }),
    });
    setSaving(false);
    if (!result.ok) {
      setError(apiErrorMessage(result.data, "Unable to save platform settings."));
      return;
    }
    setNotice("Platform settings saved.");
  }

  if (loading) {
    return (
      <div className="panel-card" style={{ maxWidth: 720, marginTop: 16 }}>
        <div className="skeleton" style={{ height: 140 }} />
      </div>
    );
  }

  return (
    <form className="panel-card resource-form" style={{ maxWidth: 720, marginTop: 16 }} onSubmit={onSubmit}>
      <div className="panel-card-header">
        <h2>Platform settings</h2>
      </div>
      {error ? <div className="alert alert-danger">{error}</div> : null}
      {notice ? <div className="alert alert-info">{notice}</div> : null}
      <div className="resource-fields">
        {PLATFORM_KEYS.map((key) => (
          <div className="form-field" key={key}>
            <label htmlFor={`setting-${key}`}>{key.replace(/_/g, " ")}</label>
            <input
              id={`setting-${key}`}
              value={values[key] || ""}
              onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))}
            />
          </div>
        ))}
      </div>
      <div className="resource-actions">
        <button className="btn-pill btn-pill-green" type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save settings"}
        </button>
      </div>
    </form>
  );
}
