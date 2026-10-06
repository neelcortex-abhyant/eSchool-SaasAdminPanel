"use client";

import { FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, apiErrorMessage, setSession } from "@/lib/api";

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
              `Server error (${result.status}). If Render was asleep, wait ~30s and retry. Check BACKEND_URL / NEON_DATABASE_URL.`,
            ),
          );
        } else {
          setError(apiErrorMessage(result.data, "Invalid email or password."));
        }
        return;
      }

      setSession(result.data.access_token);
      const next = searchParams.get("next");
      router.push(next && next.startsWith("/") ? next : "/");
      router.refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`Network error contacting /api/v1/auth/login. (${message})`);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="container py-5" style={{ maxWidth: 480 }}>
      <h1 className="h3 mb-3">Admin login</h1>
      <p className="text-muted small mb-3">
        Posts to <code>/api/v1/auth/login</code> on FastAPI (Bearer token).
      </p>
      <form onSubmit={onSubmit} className="border rounded p-4">
        {error ? <div className="alert alert-danger">{error}</div> : null}

        <label className="form-label" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          type="email"
          className="form-control mb-3"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="username"
          required
        />

        <label className="form-label" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          className="form-control mb-3"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
        />

        <button className="btn btn-primary w-100" type="submit" disabled={pending}>
          {pending ? "Signing in…" : "Login"}
        </button>
      </form>
    </main>
  );
}
