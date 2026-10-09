"use client";

import { FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, apiErrorMessage, setSession } from "@/lib/api";
import { IconLogoMark } from "@/lib/icons";

type LoginResponse = {
  access_token?: string;
  token_type?: string;
  expires_at?: string;
  user?: {
    email?: string;
    first_name?: string;
    last_name?: string;
    role?: string;
  };
  detail?: string;
};

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setPending(true);

    try {
      const result = await api<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      if (!result.ok || !result.data.access_token) {
        if (result.status >= 500) {
          setError(
            apiErrorMessage(
              result.data,
              `Server error (${result.status}). If the API was asleep, wait ~30s and retry.`,
            ),
          );
        } else {
          setError(apiErrorMessage(result.data, "Invalid email or password."));
        }
        return;
      }

      setSession(result.data.access_token);
      const next = searchParams.get("next");
      const home = result.data.user?.role === "school_admin" ? "/school" : "/dashboard";
      router.push(next && next.startsWith("/") && next !== "/" ? next : home);
      router.refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`Network error contacting login API. (${message})`);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="login-page">
      <div className="login-card">
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
          <div className="sidebar-logo" aria-hidden>
            <IconLogoMark width={22} height={22} />
          </div>
          <div>
            <div className="sidebar-brand-name">SchoolSarthi</div>
            <div className="sidebar-brand-sub">Admin sign in</div>
          </div>
        </div>

        <h1>Welcome back</h1>
        <p className="muted">Enter your credentials to access the administration portal.</p>

        <form onSubmit={onSubmit}>
          {error ? <div className="alert alert-danger">{error}</div> : null}

          <div className="form-field">
            <label htmlFor="email">Email address</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="username"
              required
            />
          </div>

          <div className="form-field">
            <label htmlFor="password">Password</label>
            <div className="password-field">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
              />
              <button
                className="password-toggle"
                type="button"
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
                onClick={() => setShowPassword((visible) => !visible)}
              >
                {showPassword ? <IconEyeOff /> : <IconEye />}
              </button>
            </div>
          </div>

          <button className="btn-primary" type="submit" disabled={pending}>
            {pending ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </main>
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
