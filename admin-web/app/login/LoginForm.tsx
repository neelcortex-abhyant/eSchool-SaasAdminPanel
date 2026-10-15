"use client";

import { FormEvent, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, apiErrorMessage, clearSession, setSession } from "@/lib/api";

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
  const portal = searchParams.get("role");
  const copy = portalCopy(portal);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [schoolCode, setSchoolCode] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showCodeHelp, setShowCodeHelp] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [pending, setPending] = useState(false);

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

      const destination = portalDestination(result.data.user?.role, portal);
      if (!destination) {
        clearSession();
        setError(portalDeniedMessage(portal));
        return;
      }
      signedIn = true;
      setSuccess("Signed in. Opening your panel.");
      setSession(result.data.access_token);
      const next = searchParams.get("next");
      router.push(!portal && next && next.startsWith("/") && next !== "/" ? next : destination);
      router.refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`Network error contacting login API. (${message})`);
    } finally {
      if (!signedIn) setPending(false);
    }
  }

  return (
    <main className="login-split">
      <section className="login-panel">
        <div className="login-panel-inner">
          <h1>{copy.title}</h1>
          <p className="login-lead">{copy.lead}</p>

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
                onClick={() =>
                  setNotice("Password reset is not available in this portal yet. Contact your platform administrator.")
                }
              >
                Forgot password?
              </button>
            </div>

            <button className="login-submit" type="submit" disabled={pending}>
              {pending && !success ? <span className="login-spinner" aria-hidden /> : null}
              {success ? "Signed in" : pending ? "Signing in…" : "Sign in →"}
            </button>
          </form>

          <p className="login-signup">
            New user? <Link href="/register-school">Sign up</Link> to manage your school activities seamlessly!
          </p>

          <div className="login-demo">
            <p>Portal roles</p>
            <span>Super admin panels</span>
            <div className="login-pills">
              <PortalLink href="/login?role=super_admin" active={portal === "super_admin"} tone="is-green">
                Super admin
              </PortalLink>
              <PortalLink href="/login?role=staff" active={portal === "staff"} tone="is-blue">
                Staff
              </PortalLink>
            </div>
            <span>School panels</span>
            <div className="login-pills">
              <PortalLink href="/login?role=school_admin" active={portal === "school_admin"} tone="is-green">
                School admin
              </PortalLink>
              <PortalLink href="/login?role=teacher" active={portal === "teacher"} tone="is-rose">
                Teacher
              </PortalLink>
              <PortalLink href="/login?role=school_staff" active={portal === "school_staff"} tone="is-blue">
                Staff
              </PortalLink>
            </div>
          </div>
        </div>
      </section>

      <aside className="login-showcase" aria-hidden>
        <Image
          src="https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1400&q=80"
          alt=""
          fill
          priority
          className="login-showcase-photo"
        />
        <div className="login-showcase-shade" />
        <div className="login-showcase-content">
          <div className="login-showcase-brand">
            <span>S</span>
            SchoolSarthi
          </div>
          <p className="login-showcase-badge">School portal</p>
          <h2>
            Empowering the
            <br />
            next generation of
            <br />
            leaders.
          </h2>
          <p>
            Streamline administrative tasks, manage student progress, and connect with your faculty all in one secure
            place.
          </p>
        </div>
      </aside>
    </main>
  );
}

function PortalLink({
  href,
  active,
  tone,
  children,
}: {
  href: string;
  active: boolean;
  tone: string;
  children: string;
}) {
  return (
    <Link href={href} className={`login-pill ${tone}${active ? " is-active" : ""}`} aria-current={active ? "page" : undefined}>
      {children}
    </Link>
  );
}

function portalCopy(role: string | null): { title: string; lead: string } {
  if (role === "super_admin") {
    return { title: "Super admin sign in", lead: "Sign in to the platform administration panel." };
  }
  if (role === "staff") {
    return { title: "Staff sign in", lead: "Sign in to the platform staff panel." };
  }
  if (role === "school_admin") {
    return { title: "School admin sign in", lead: "Sign in to your school panel." };
  }
  if (role === "teacher") {
    return { title: "Teacher sign in", lead: "Sign in to the teacher panel." };
  }
  if (role === "school_staff") {
    return { title: "Staff sign in", lead: "Sign in to the school staff panel." };
  }
  return { title: "Welcome back!", lead: "Enter your credentials to access your academic portal." };
}

function portalDestination(accountRole: string | undefined, requested: string | null): string | null {
  if (requested === "super_admin") return accountRole === "super_admin" ? "/dashboard" : null;
  if (requested === "school_admin") return accountRole === "school_admin" ? "/school" : null;
  if (requested === "teacher" || requested === "staff" || requested === "school_staff") return null;
  if (accountRole === "school_admin") return "/school";
  return "/dashboard";
}

function portalDeniedMessage(requested: string | null): string {
  if (requested === "super_admin") return "This account cannot sign in to the super admin panel.";
  if (requested === "school_admin") return "This account cannot sign in to the school admin panel.";
  if (requested === "teacher") return "Teacher sign-in is not available for this account.";
  if (requested === "staff" || requested === "school_staff") return "Staff sign-in is not available for this account.";
  return "This account cannot sign in here.";
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
