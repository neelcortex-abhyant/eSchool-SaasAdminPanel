"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import LoginShowcase from "@/components/login/LoginShowcase";
import { api, apiErrorMessage, setSession } from "@/lib/api";

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
  // Query params are read in the browser rather than with useSearchParams, which would
  // force the whole form out of the server HTML behind a "Loading…" placeholder.
  const [mode, setMode] = useState<"sign-in" | "forgot">("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [schoolCode, setSchoolCode] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showCodeHelp, setShowCodeHelp] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("forgot") === "1") setMode("forgot");
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");
    setSuccess("");
    setPending(true);
    let signedIn = false;

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

      signedIn = true;
      setSuccess("Signed in. Opening your panel.");
      setSession(result.data.access_token);
      const next = new URLSearchParams(window.location.search).get("next");
      const destination = result.data.user?.role === "school_admin" ? "/school" : "/dashboard";
      router.push(next && next.startsWith("/") && next !== "/" ? next : destination);
      router.refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`Network error contacting login API. (${message})`);
    } finally {
      if (!signedIn) setPending(false);
    }
  }

  async function onForgot(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");
    setSuccess("");
    setPending(true);
    try {
      const result = await api<{ message?: string }>("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email, app_origin: window.location.origin }),
      });
      if (!result.ok) {
        if (result.status === 404) {
          setError("Password reset is not available on the sign-in service yet.");
        } else {
          setError(apiErrorMessage(result.data, "Could not send the reset email."));
        }
        return;
      }
      setSuccess(result.data.message || "If an account exists for that email, a reset link has been sent.");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`Network error contacting login API. (${message})`);
    } finally {
      setPending(false);
    }
  }

  function showSignIn() {
    setMode("sign-in");
    setError("");
    setNotice("");
    setSuccess("");
  }

  return (
    <main className="login-split">
      <section className="login-panel">
        <div className="login-panel-inner">
          <Link href="/" className="login-home">
            ← Home
          </Link>
          <h1>{mode === "forgot" ? "Reset your password" : "Welcome back!"}</h1>
          <p className="login-lead">
            {mode === "forgot"
              ? "Enter your account email. We'll send a link to choose a new password."
              : "Enter your credentials to access your academic portal."}
          </p>

          {mode === "forgot" ? (
            <form className="login-form" onSubmit={onForgot} aria-busy={pending}>
              {pending ? (
                <div className="alert alert-info login-status" role="status">
                  <span className="login-spinner is-dark" aria-hidden />
                  Sending reset link…
                </div>
              ) : null}
              {success ? (
                <div className="alert alert-success login-status" role="status">
                  {success}
                </div>
              ) : null}
              {error ? (
                <div className="alert alert-danger" role="alert">
                  {error}
                </div>
              ) : null}

              <div className="form-field">
                <label htmlFor="reset-email">Email address</label>
                <div className="login-input">
                  <MailIcon />
                  <input
                    id="reset-email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="name@example.com"
                    autoComplete="username"
                    required
                    disabled={pending || Boolean(success)}
                  />
                </div>
              </div>

              <button className="login-submit" type="submit" disabled={pending || Boolean(success)}>
                {pending ? <span className="login-spinner" aria-hidden /> : null}
                {success ? "Reset link sent" : pending ? "Sending…" : "Send reset link"}
              </button>
              <p className="login-signup">
                <button className="link-btn" type="button" onClick={showSignIn}>
                  Back to sign in
                </button>
              </p>
            </form>
          ) : (
          <form className="login-form" onSubmit={onSubmit} aria-busy={pending}>
            {pending && !success ? (
              <div className="alert alert-info login-status" role="status">
                <span className="login-spinner is-dark" aria-hidden />
                Signing in…
              </div>
            ) : null}
            {success ? (
              <div className="alert alert-success login-status" role="status">
                {success}
              </div>
            ) : null}
            {error ? (
              <div className="alert alert-danger" role="alert">
                {error}
              </div>
            ) : null}
            {notice ? <div className="alert alert-info">{notice}</div> : null}

            <div className="form-field">
              <label htmlFor="email">Email address</label>
              <div className="login-input">
                <MailIcon />
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="name@example.com"
                  autoComplete="username"
                  required
                  disabled={pending}
                />
              </div>
            </div>

            <div className="form-field">
              <label htmlFor="password">Password</label>
              <div className="login-input">
                <LockIcon />
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                  disabled={pending}
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
              <div className="login-label-row">
                <label htmlFor="school-code">School code</label>
                <button className="link-btn" type="button" onClick={() => setShowCodeHelp((open) => !open)}>
                  What&apos;s this?
                </button>
              </div>
              <div className="login-input">
                <BuildingIcon />
                <input
                  id="school-code"
                  value={schoolCode}
                  onChange={(event) => setSchoolCode(event.target.value)}
                  placeholder="SCH-XXXX"
                  autoComplete="off"
                  disabled={pending}
                />
              </div>
              {showCodeHelp ? (
                <p className="field-hint">
                  School code is shown here for reference. This sign-in uses your email and password.
                </p>
              ) : null}
            </div>

            <div className="login-forgot">
              <button
                className="link-btn"
                type="button"
                onClick={() => {
                  setMode("forgot");
                  setError("");
                  setNotice("");
                  setSuccess("");
                }}
              >
                Forgot password?
              </button>
            </div>

            <button className="login-submit" type="submit" disabled={pending}>
              {pending && !success ? <span className="login-spinner" aria-hidden /> : null}
              {success ? "Signed in" : pending ? "Signing in…" : "Sign in →"}
            </button>

            <p className="login-signup">
              New user? <Link href="/register-school">Sign up</Link> to manage your school activities seamlessly!
            </p>
          </form>
          )}
        </div>
      </section>

      <LoginShowcase />
    </main>
  );
}

function MailIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m4 7 8 6 8-6" />
    </svg>
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

function BuildingIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <path d="M4 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16" />
      <path d="M14 10h5a1 1 0 0 1 1 1v10" />
      <path d="M8 8h2M8 12h2M8 16h2" />
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
