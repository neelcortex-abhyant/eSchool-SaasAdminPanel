"use client";

import { useCallback, useState } from "react";
import { AccessGate, useSchoolAdminAccess } from "@/components/academics/AcademicPage";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { TextField } from "@/components/academics/Fields";
import { useOptions } from "@/components/academics/hooks";
import { ToastProvider, useToast } from "@/components/academics/Toasts";
import { Chip, formatDateTime, type ChipTone } from "@/components/teaching/Frame";
import { domainSettings, mySite, setCustomDomain, verifyDomain } from "@/lib/domains/client";
import { customDomainProblem } from "@/lib/domains/core";
import { domainsLive, domainsMock, domainsMode } from "@/lib/domains/mode";
import { setupSteps } from "@/lib/domains/theme";
import type { DomainSettings, DomainStatus } from "@/lib/domains/types";
import { IconGlobe } from "@/lib/icons";

const STATUS: Record<DomainStatus, { label: string; tone: ChipTone }> = {
  not_started: { label: "Not connected", tone: "grey" },
  pending: { label: "Waiting for DNS", tone: "amber" },
  verified: { label: "Connected", tone: "green" },
  failed: { label: "Check failed", tone: "red" },
};

export default function WebsitePage() {
  const access = useSchoolAdminAccess();
  return (
    <ToastProvider>
      <div className="acad-page teach-page">
        <header className="acad-header">
          <div className="school-dash-title">
            <span className="school-dash-title-icon" aria-hidden>
              <IconGlobe width={18} height={18} />
            </span>
            <div>
              <h1>Website & domain</h1>
              <p className="muted acad-subtitle">Your school's public website, its address, and what's left to set up.</p>
            </div>
          </div>
        </header>
        <div className="alert alert-info acad-mock-note">
          {domainsLive()
            ? "Connected to the school's server."
            : domainsMock()
              ? "Sample data saved only in this browser."
              : "Your school's address comes from the school's server. The public website goes live once the server can serve school websites (see backend/docs/SCHOOL_DOMAINS_API_CONTRACT.md); until then use Preview to see it with your school's details."}
        </div>
        <AccessGate access={access}>
          <WebsiteBody />
        </AccessGate>
      </div>
    </ToastProvider>
  );
}

function WebsiteBody() {
  const toast = useToast();
  const state = useOptions(
    useCallback(async () => {
      const settings = await domainSettings();
      return [{ settings, site: await mySite(settings.slug).catch(() => null) }];
    }, []),
  );
  const data = state.options[0] ?? null;
  const [override, setOverride] = useState<DomainSettings | null>(null);
  const settings = override ?? data?.settings ?? null;
  const [draft, setDraft] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<DomainSettings>, success: string) {
    setBusy(true);
    try {
      const next = await action();
      setOverride(next);
      toast(next.last_error ? "error" : "success", next.last_error || success);
    } catch (caught) {
      const error = caught as Error & { field?: string };
      if (error.field) setFieldError(error.message);
      else toast("error", error.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  if (state.error) return <ErrorAlert error={state.error} onRetry={() => void state.reload()} />;
  if (!settings) return <div className="resource-card"><div className="skeleton" style={{ height: 220 }} /></div>;
  const steps = data?.site ? setupSteps({ ...data.site, custom_domain: settings.custom_domain, domain_status: settings.domain_status }) : [];
  const done = steps.filter((step) => step.done).length;

  return (
    <>
      <section className="resource-card" aria-labelledby="site-title">
        <div className="teach-detail-head">
          <div>
            <h2 id="site-title" className="teach-section-title">Your website</h2>
            <p>
              {settings.default_url ? (
                <>
                  <strong>{settings.default_url.replace(/^https?:\/\//, "")}</strong>{" "}
                  {domainsMode() === "pending" ? <Chip tone="amber">Reserved · goes live when school websites are switched on</Chip> : <Chip tone="green">Live</Chip>}
                </>
              ) : (
                <span className="muted">No default address yet. It's set when the school registers with a default domain; ask the platform team to add one.</span>
              )}
            </p>
            {settings.custom_domain && settings.domain_status === "verified" ? (
              <p>
                Also at{" "}
                <a href={`https://${settings.custom_domain}`} target="_blank" rel="noopener noreferrer">
                  {settings.custom_domain}
                </a>
              </p>
            ) : null}
          </div>
          <div className="teach-detail-actions">
            <a className="btn-pill btn-pill-green" href="/site-preview" target="_blank" rel="noopener noreferrer">
              Preview my website
            </a>
            {settings.default_url && domainsMode() !== "pending" ? (
              <a className="btn-pill btn-pill-green-soft" href={settings.custom_domain && settings.domain_status === "verified" ? `https://${settings.custom_domain}` : settings.default_url} target="_blank" rel="noopener noreferrer">
                View website
              </a>
            ) : null}
          </div>
        </div>
      </section>

      {steps.length ? (
        <section className="resource-card" aria-labelledby="setup-title">
          <h2 id="setup-title" className="teach-section-title">
            Setup checklist · {done} of {steps.length} done
          </h2>
          <p className="muted">Until every step is done, your website shows “Our online portal is being set up”.</p>
          <ul className="domain-checklist">
            {steps.map((step) => (
              <li key={step.key} className={step.done ? "is-done" : undefined}>
                <span aria-hidden>{step.done ? "✓" : "○"}</span> {step.label}
                {step.done ? <span className="acad-sr"> (done)</span> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="resource-card" aria-labelledby="domain-title">
        <h2 id="domain-title" className="teach-section-title">
          Custom domain {settings.custom_domain ? <Chip tone={STATUS[settings.domain_status].tone}>{STATUS[settings.domain_status].label}</Chip> : null}
        </h2>
        {settings.custom_domain ? (
          <>
            <p>
              <strong>{settings.custom_domain}</strong>
              {settings.last_checked_at ? <span className="muted"> · last checked {formatDateTime(settings.last_checked_at)}</span> : null}
            </p>
            {settings.last_error ? <div className="alert alert-warning">{settings.last_error}</div> : null}
            {settings.domain_status !== "verified" && settings.verification ? (
              <>
                <p>Add these two records at your domain provider (where you bought the domain), then press Check now. Changes can take a few minutes to 48 hours to appear.</p>
                <div className="table-wrap">
                  <table className="data-table domain-dns">
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>Name / host</th>
                        <th>Value / points to</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>TXT</td>
                        <td><code>{settings.verification.txt_name}</code></td>
                        <td><code>{settings.verification.txt_value}</code></td>
                      </tr>
                      <tr>
                        <td>CNAME</td>
                        <td><code>{settings.verification.cname_name}</code></td>
                        <td><code>{settings.verification.cname_target}</code></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p className="muted">Your website stays at {settings.default_url.replace(/^https?:\/\//, "")} until the check succeeds.</p>
              </>
            ) : null}
            <div className="teach-toolbar">
              {settings.domain_status !== "verified" ? (
                <button className="btn-pill btn-pill-green" type="button" disabled={busy} onClick={() => void run(verifyDomain, "Domain connected.")}>
                  {busy ? "Checking…" : "Check now"}
                </button>
              ) : null}
              <button className="btn-pill btn-pill-green-soft" type="button" disabled={busy} onClick={() => void run(() => setCustomDomain(null), "Custom domain removed.")}>
                Remove custom domain
              </button>
            </div>
          </>
        ) : domainsMode() === "pending" ? (
          <p className="muted">
            Connecting your own domain (e.g. portal.yourschool.edu) isn't available on the school's server yet. You can choose a custom domain when registering a
            school, or ask the platform team to set one up.
          </p>
        ) : (
          <form
            className="teach-inline-form"
            onSubmit={(event) => {
              event.preventDefault();
              const problem = customDomainProblem(draft);
              setFieldError(problem);
              if (!problem) void run(() => setCustomDomain(draft), "Domain saved. Add the DNS records below, then press Check now.");
            }}
          >
            <TextField id="custom-domain" label="Your domain" placeholder="portal.yourschool.edu" value={draft} onChange={(value) => { setDraft(value); setFieldError(""); }} error={fieldError} />
            <button className="btn-pill btn-pill-green" type="submit" disabled={busy}>
              Connect domain
            </button>
          </form>
        )}
      </section>
    </>
  );
}
