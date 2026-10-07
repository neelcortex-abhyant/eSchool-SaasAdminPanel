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
  };
  detail?: string;
};

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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
      router.push(next && next.startsWith("/") && next !== "/" ? next : "/dashboard");
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
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          <button className="btn-primary" type="submit" disabled={pending}>
            {pending ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </main>
  );
}
