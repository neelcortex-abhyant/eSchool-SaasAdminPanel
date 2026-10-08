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
    </div>
  );
}
