"use client";

import { FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setPending(true);

    try {
      const result = await api<{
        error?: boolean;
        message?: string;
        requires_2fa?: boolean;
      }>("/login", {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
          code: code || null,
        }),
      });

      if (!result.ok || result.data.error) {
        setError(result.data.message || "Login failed.");
        return;
      }

      if (result.data.requires_2fa) {
        setError("Two-factor authentication is required before continuing.");
        return;
      }

      const next = searchParams.get("next");
      router.push(next && next.startsWith("/") ? next : "/");
      router.refresh();
    } catch {
      setError("Network error contacting /api/admin.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="container py-5" style={{ maxWidth: 480 }}>
      <h1 className="h3 mb-3">Admin login</h1>
      <p className="text-muted small mb-3">
        Posts to <code>/api/admin/login</code> via FastAPI.
      </p>
      <form onSubmit={onSubmit} className="border rounded p-4">
        {error ? <div className="alert alert-danger">{error}</div> : null}

        <label className="form-label" htmlFor="email">
          Email or mobile
        </label>
        <input
          id="email"
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

        <label className="form-label" htmlFor="code">
          School code
        </label>
        <input
          id="code"
          className="form-control mb-3"
          value={code}
          onChange={(event) => setCode(event.target.value)}
          placeholder="Leave empty for super admin"
        />

        <button className="btn btn-primary w-100" type="submit" disabled={pending}>
          {pending ? "Signing in…" : "Login"}
        </button>
      </form>
    </main>
  );
}
