"use client";

import { FormEvent, Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import LoginShowcase from "@/components/login/LoginShowcase";
import { api, apiErrorMessage } from "@/lib/api";

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <main className="login-split">
          <section className="login-panel">
            <p className="muted">Loading…</p>
          </section>
        </main>
      }
    >
      <ResetPasswordForm />
    </Suspense>
  );
}

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (password !== confirm) {
      setError("New password and confirmation must match.");
      return;
    }
    setPending(true);
    try {
      const result = await api<{ message?: string }>("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({
          token,
          new_password: password,
          confirm_password: confirm,
        }),
      });
      if (!result.ok) {
        if (result.status === 404) {
          setError("Password reset is not available on the sign-in service yet.");
        } else {
          setError(apiErrorMessage(result.data, "Could not update the password."));
        }
        return;
      }
      setSuccess(result.data.message || "Password updated.");
      setPassword("");
      setConfirm("");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`Network error contacting login API. (${message})`);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="login-split">
      <section className="login-panel">
        <div className="login-panel-inner">
          <h1>Choose a new password</h1>
          <p className="login-lead">Use at least 8 characters. This link works once.</p>

          {!token ? (
            <div className="alert alert-danger" role="alert">
              This reset link is missing or invalid. Request a new one from the sign-in page.
            </div>
          ) : (
            <form className="login-form" onSubmit={onSubmit} aria-busy={pending}>
              {pending ? (
                <div className="alert alert-info login-status" role="status">
                  <span className="login-spinner is-dark" aria-hidden />
                  Updating password…
                </div>
              ) : null}
              {success ? (
                <div className="alert alert-success login-status" role="status">
                  {success} You can sign in with the new password.
                </div>
              ) : null}
              {error ? (
                <div className="alert alert-danger" role="alert">
                  {error}
                </div>
              ) : null}

              <div className="form-field">
                <label htmlFor="new-password">New password</label>
                <div className="login-input">
                  <LockIcon />
                  <input
                    id="new-password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="••••••••"
                    autoComplete="new-password"
                    minLength={8}
                    required
                    disabled={pending || Boolean(success)}
                  />
                  <button
                    className="password-toggle login-eye"
                    type="button"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((visible) => !visible)}
                  >
                    {showPassword ? <IconEyeOff /> : <IconEye />}
                  </button>
                </div>
              </div>

              <div className="form-field">
                <label htmlFor="confirm-password">Confirm password</label>
                <div className="login-input">
                  <LockIcon />
                  <input
                    id="confirm-password"
                    type={showPassword ? "text" : "password"}
                    value={confirm}
                    onChange={(event) => setConfirm(event.target.value)}
                    placeholder="••••••••"
                    autoComplete="new-password"
                    minLength={8}
                    required
                    disabled={pending || Boolean(success)}
                  />
                </div>
              </div>

              <button className="login-submit" type="submit" disabled={pending || Boolean(success)}>
                {pending ? <span className="login-spinner" aria-hidden /> : null}
                {success ? "Password updated" : pending ? "Updating…" : "Update password"}
              </button>
            </form>
          )}

          <p className="login-signup">
            <Link href="/login">Back to sign in</Link>
          </p>
        </div>
      </section>
      <LoginShowcase />
    </main>
  );
}

function LockIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

function IconEye() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" />
      <circle cx="12" cy="12" r="2.5" />
    </svg>
  );
}

function IconEyeOff() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <path d="M3 3l18 18" />
      <path d="M10.6 10.6A2.5 2.5 0 0 0 12 14.5c.6 0 1.1-.2 1.5-.5" />
      <path d="M9.9 5.2A10.8 10.8 0 0 1 12 5c6.5 0 10 7 10 7a18.4 18.4 0 0 1-3.2 4.1" />
      <path d="M6.1 6.1C3.5 7.9 2 12 2 12s3.5 6 10 6c1.4 0 2.7-.3 3.8-.8" />
    </svg>
  );
}
