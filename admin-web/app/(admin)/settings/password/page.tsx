"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { api, apiErrorMessage } from "@/lib/api";

export default function ChangePasswordPage() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setNotice("");
    if (!currentPassword || !newPassword || !confirmPassword) {
      setError("Enter your current password, a new password, and the confirmation.");
      return;
    }
    if (newPassword.length < 8) {
      setError("The new password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation must match.");
      return;
    }
    if (newPassword === currentPassword) {
      setError("Choose a different password.");
      return;
    }
    setSaving(true);
    setError("");
    const result = await api<{ message?: string }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      }),
    });
    setSaving(false);
    if (!result.ok) {
      setError(apiErrorMessage(result.data, "Unable to change your password."));
      return;
    }
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setNotice(result.data.message || "Password changed.");
  }

  return (
    <div>
      <h1 className="profile-title">Change password</h1>
      <form className="panel-card profile-form" style={{ maxWidth: 520 }} onSubmit={onSubmit}>
        {error ? <div className="alert alert-danger" role="alert">{error}</div> : null}
        {notice ? <div className="alert alert-success">{notice}</div> : null}
        <div className="form-field">
          <label htmlFor="current-password">Current password *</label>
          <input
            id="current-password"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            required
          />
        </div>
        <div className="form-field">
          <label htmlFor="new-password">New password *</label>
          <input
            id="new-password"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            minLength={8}
            required
          />
        </div>
        <div className="form-field">
          <label htmlFor="confirm-password">Confirm password *</label>
          <input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            minLength={8}
            required
          />
        </div>
        <button className="profile-submit" type="submit" disabled={saving}>
          {saving ? "Saving…" : "Change password"}
        </button>
        <p className="school-empty-note">
          <Link href="/settings">Back to profile</Link>
        </p>
      </form>
    </div>
  );
}
