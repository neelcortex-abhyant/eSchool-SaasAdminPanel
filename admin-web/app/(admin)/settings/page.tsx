"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";

const DIAL_CODES = ["+93", "+91", "+1", "+44", "+61", "+971", "+966", "+92", "+880", "+977", "+94", "+86", "+81", "+82", "+65", "+60", "+27", "+234", "+254", "+33", "+49"];

type Profile = {
  id?: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  mobile?: string | null;
  country_code?: string | null;
  gender?: string | null;
  image?: string | null;
  dob?: string | null;
  current_address?: string | null;
  permanent_address?: string | null;
  two_factor_enabled?: number;
  role?: string;
  detail?: unknown;
};

function splitMobile(value: string, countryCode?: string | null) {
  const trimmed = value.trim();
  if (countryCode) return { code: countryCode, number: trimmed };
  const codes = [...DIAL_CODES].sort((a, b) => b.length - a.length);
  const match = codes.find((code) => trimmed.startsWith(code));
  if (!match) return { code: "+91", number: trimmed };
  return { code: match, number: trimmed.slice(match.length).trim() };
}

function rejectedExtraFields(data: unknown) {
  if (!data || typeof data !== "object") return false;
  const detail = (data as { detail?: unknown }).detail;
  const text = JSON.stringify(detail || "").toLowerCase();
  return text.includes("extra") || text.includes("country_code") || text.includes("gender");
}

export default function SettingsPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [dialCode, setDialCode] = useState("+91");
  const [mobile, setMobile] = useState("");
  const [gender, setGender] = useState("");
  const [dob, setDob] = useState("");
  const [currentAddress, setCurrentAddress] = useState("");
  const [permanentAddress, setPermanentAddress] = useState("");
  const [image, setImage] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [twoFactor, setTwoFactor] = useState(false);
  const [uploading, setUploading] = useState(false);
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
      const phone = splitMobile(result.data.mobile || "", result.data.country_code);
      setProfile(result.data);
      setFirstName(result.data.first_name || "");
      setLastName(result.data.last_name || "");
      setDialCode(phone.code);
      setMobile(phone.number);
      setGender(result.data.gender || "");
      setDob((result.data.dob || "").slice(0, 10));
      setCurrentAddress(result.data.current_address || "");
      setPermanentAddress(result.data.permanent_address || "");
      setImage(result.data.image || "");
      setTwoFactor(result.data.two_factor_enabled === 1);
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
    if (!gender) {
      setError("Select a gender.");
      return;
    }
    if (!dob) {
      setError("Enter a date of birth.");
      return;
    }
    if (!currentAddress.trim() || !permanentAddress.trim()) {
      setError("Enter the current and permanent address.");
      return;
    }
    setSaving(true);
    setError("");
    const fullBody = {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      mobile: mobile.trim() || null,
      country_code: dialCode,
      gender,
      dob,
      current_address: currentAddress.trim(),
      permanent_address: permanentAddress.trim(),
      image: image || null,
      two_factor_enabled: twoFactor ? 1 : 0,
    };
    let result = await api<Profile>("/users/me", { method: "PATCH", body: JSON.stringify(fullBody) });
    let partial = false;
    if (!result.ok && (rejectedExtraFields(result.data) || result.status >= 500)) {
      result = await api<Profile>("/users/me", {
        method: "PATCH",
        body: JSON.stringify({
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          mobile: `${dialCode} ${mobile.trim()}`.trim().slice(0, 32) || null,
        }),
      });
      partial = result.ok;
    }
    setSaving(false);
    if (!result.ok) {
      setError(apiErrorMessage(result.data, "Unable to update your profile."));
      return;
    }
    setProfile(result.data);
    setNotice(partial ? "Name and mobile were saved. The current account API does not store the other profile fields yet." : "Profile updated.");
  }

  async function uploadImage() {
    if (!imageFile) {
      setError("Choose an image first.");
      return;
    }
    setUploading(true);
    setError("");
    const body = new FormData();
    body.set("file", imageFile);
    const response = await fetch("/api/school-logos", { method: "POST", body });
    const data = (await response.json().catch(() => ({}))) as { logo?: string; detail?: string };
    setUploading(false);
    if (!response.ok || !data.logo) {
      setError(typeof data.detail === "string" ? data.detail : "Unable to upload this image.");
      return;
    }
    setImage(data.logo);
    setNotice("Image uploaded. Submit the profile to save it.");
  }

  return (
    <div>
      <h1 className="profile-title">Profile</h1>

      {loading ? (
        <div className="panel-card">
          <div className="skeleton" style={{ height: 18, width: "40%", marginBottom: 12 }} />
          <div className="skeleton" style={{ height: 220 }} />
        </div>
      ) : (
        <form className="panel-card profile-form" onSubmit={onSubmit}>
          {error ? <div className="alert alert-danger">{error}</div> : null}
          {notice ? <div className="alert alert-success">{notice}</div> : null}
          <div className="profile-grid">
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
              <div className="profile-phone">
                <select aria-label="Country code" value={dialCode} onChange={(event) => setDialCode(event.target.value)}>
                  {DIAL_CODES.map((code) => (
                    <option key={code} value={code}>{code}</option>
                  ))}
                </select>
                <input id="profile-mobile" inputMode="tel" value={mobile} onChange={(e) => setMobile(e.target.value)} maxLength={20} />
              </div>
            </div>
            <fieldset className="form-field profile-gender">
              <legend>Gender *</legend>
              <label><input type="radio" name="gender" value="male" checked={gender === "male"} onChange={() => setGender("male")} /> Male</label>
              <label><input type="radio" name="gender" value="female" checked={gender === "female"} onChange={() => setGender("female")} /> Female</label>
            </fieldset>
            <div className="form-field">
              <label htmlFor="profile-image">Image</label>
              <div className="profile-upload">
                <input id="profile-image" type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={(event) => setImageFile(event.target.files?.[0] || null)} />
                <button className="profile-upload-btn" type="button" onClick={() => void uploadImage()} disabled={uploading}>
                  {uploading ? "Uploading…" : "Upload"}
                </button>
              </div>
              {image ? <img className="profile-avatar" src={image} alt="" /> : <span className="profile-avatar" aria-hidden>👤</span>}
            </div>
            <div className="form-field">
              <label htmlFor="profile-dob">Date of birth *</label>
              <input id="profile-dob" type="date" value={dob} onChange={(event) => setDob(event.target.value)} required />
            </div>
            <div className="form-field">
              <label htmlFor="profile-email">Email *</label>
              <input id="profile-email" type="email" value={profile?.email || ""} readOnly />
            </div>
            <div className="form-field">
              <label htmlFor="profile-current">Current address *</label>
              <textarea id="profile-current" value={currentAddress} onChange={(event) => setCurrentAddress(event.target.value)} required maxLength={512} />
            </div>
            <div className="form-field">
              <label htmlFor="profile-permanent">Permanent address *</label>
              <textarea id="profile-permanent" value={permanentAddress} onChange={(event) => setPermanentAddress(event.target.value)} required maxLength={512} />
            </div>
          </div>
          <label className="profile-check">
            <input type="checkbox" checked={twoFactor} onChange={(event) => setTwoFactor(event.target.checked)} />
            Two factor verification
          </label>
          <button className="profile-submit" type="submit" disabled={saving || uploading}>
            {saving ? "Saving…" : "Submit"}
          </button>
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
