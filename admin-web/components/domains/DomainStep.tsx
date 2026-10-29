"use client";

import { useEffect, useRef, useState } from "react";
import { useDebounced } from "@/components/academics/hooks";
import { checkAvailability } from "@/lib/domains/client";
import { customDomainProblem, defaultSlug, rootDomain, slugAlternatives } from "@/lib/domains/core";
import type { Availability } from "@/lib/domains/types";

export type DomainDraft = {
  type: "default" | "custom";
  slug: string;
  /** The admin changed the subdomain by hand, so it no longer follows the school name. */
  slugEdited: boolean;
  custom_domain: string;
};

/** What the admin types, kept to subdomain characters; a trailing hyphen stays while typing (the check flags it). */
export function typedSlug(input: string): string {
  return input
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-+/, "")
    .slice(0, 40);
}

export const EMPTY_DOMAIN: DomainDraft = { type: "default", slug: "", slugEdited: false, custom_domain: "" };

export type DomainCheck = { state: "idle" | "checking" | "done" | "error"; result: Availability | null; message: string };

/**
 * The registration form's "School domain" step: a default subdomain made from the school name
 * (checked as the admin types, with readable alternatives when taken), or the school's own domain,
 * which is connected after DNS verification. Either way the school gets a default subdomain.
 */
export function DomainStep({
  name,
  city,
  value,
  onChange,
  check,
  onCheck,
  errors,
  taken = [],
}: {
  name: string;
  city: string;
  value: DomainDraft;
  onChange: (next: DomainDraft) => void;
  check: DomainCheck;
  onCheck: (next: DomainCheck) => void;
  errors: { slug?: string; custom_domain?: string };
  /** Subdomains the server reported as taken (no availability route yet). */
  taken?: string[];
}) {
  const root = rootDomain();
  const suggested = defaultSlug(name);
  const slug = value.slugEdited ? value.slug : suggested;
  const debounced = useDebounced(slug, 400);
  const requestId = useRef(0);
  const [customTouched, setCustomTouched] = useState(false);

  // Keep the stored slug in step with the name until the admin edits it.
  useEffect(() => {
    if (!value.slugEdited && value.slug !== suggested) onChange({ ...value, slug: suggested });
  }, [suggested, value, onChange]);

  useEffect(() => {
    if (!debounced) {
      onCheck({ state: "idle", result: null, message: "" });
      return;
    }
    const id = ++requestId.current;
    onCheck({ state: "checking", result: null, message: "" });
    checkAvailability(debounced, { name, city })
      .then((result) => id === requestId.current && onCheck({ state: "done", result, message: "" }))
      .catch((error: unknown) => id === requestId.current && onCheck({ state: "error", result: null, message: error instanceof Error ? error.message : "Couldn't check the subdomain." }));
    // name/city only refine suggestions; re-checking on every keystroke there isn't needed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  const customProblem = value.type === "custom" && (customTouched || errors.custom_domain) ? errors.custom_domain || customDomainProblem(value.custom_domain, root) : "";
  const takenHere = taken.includes(slug);
  const slugError = (takenHere ? errors.slug || `${slug}.${root} is taken.` : errors.slug && !value.slugEdited ? errors.slug : "") || (check.state === "done" && check.result && !check.result.available ? check.result.problem : "");
  const alternatives =
    check.state === "done" && check.result && !check.result.available && check.result.suggestions.length
      ? check.result.suggestions
      : takenHere
        ? slugAlternatives(slug, { name, city }, (candidate) => taken.includes(candidate))
        : [];

  return (
    <fieldset className="register-section domain-step">
      <legend>School domain</legend>
      <div className="domain-options" role="radiogroup" aria-label="Domain type">
        <label className={`domain-option${value.type === "default" ? " is-selected" : ""}`}>
          <input type="radio" name="domain-type" value="default" checked={value.type === "default"} onChange={() => onChange({ ...value, type: "default" })} />
          <span>
            <strong>Default domain</strong>
            <small>Ready right away: a school website at an address made from your school's name.</small>
          </span>
        </label>
        <label className={`domain-option${value.type === "custom" ? " is-selected" : ""}`}>
          <input type="radio" name="domain-type" value="custom" checked={value.type === "custom"} onChange={() => onChange({ ...value, type: "custom" })} />
          <span>
            <strong>Custom domain</strong>
            <small>Use your school's own domain, e.g. portal.yourschool.edu, once you've added two DNS records.</small>
          </span>
        </label>
      </div>

      <div className="resource-fields">
        <div className="form-field field-span">
          <label htmlFor="reg-subdomain">{value.type === "default" ? "Your school's address" : "Default address (used until your domain is connected)"}</label>
          <div className={`domain-input${slugError ? " invalid" : ""}`}>
            <input
              id="reg-subdomain"
              value={slug}
              maxLength={40}
              autoComplete="off"
              spellCheck={false}
              placeholder={name ? "" : "enter the school name first"}
              aria-invalid={Boolean(slugError)}
              aria-describedby="reg-subdomain-status"
              onChange={(event) => onChange({ ...value, slug: typedSlug(event.target.value), slugEdited: true })}
            />
            <span className="domain-suffix">.{root}</span>
          </div>
          <div id="reg-subdomain-status" className="domain-status" aria-live="polite">
            {!slug ? (
              <span className="field-hint">The address is made from the school name.</span>
            ) : slugError ? (
              <span className="field-error">{slugError}</span>
            ) : check.state === "checking" ? (
              <span className="field-hint">Checking {slug}.{root}…</span>
            ) : check.state === "error" ? (
              <span className="field-error">{check.message} You can still submit; the server checks again.</span>
            ) : check.state === "done" && check.result?.available && check.result.unchecked ? (
              <span className="field-hint">{slug}.{root} — we'll confirm it's free when you submit.</span>
            ) : check.state === "done" && check.result?.available ? (
              <span className="domain-ok">✓ {slug}.{root} is available</span>
            ) : null}
          </div>
          {alternatives.length ? (
            <div className="domain-suggestions">
              <span className="field-hint">Try:</span>
              {alternatives.map((option) => (
                <button key={option} className="btn-pill btn-pill-green-soft" type="button" onClick={() => onChange({ ...value, slug: option, slugEdited: true })}>
                  {option}.{root}
                </button>
              ))}
            </div>
          ) : null}
          {value.slugEdited && suggested && slug !== suggested ? (
            <button className="link-btn" type="button" onClick={() => onChange({ ...value, slug: suggested, slugEdited: false })}>
              Use {suggested}.{root} from the school name
            </button>
          ) : null}
        </div>

        {value.type === "custom" ? (
          <div className="form-field field-span">
            <label htmlFor="reg-custom-domain">Your domain *</label>
            <input
              id="reg-custom-domain"
              value={value.custom_domain}
              maxLength={253}
              autoComplete="off"
              spellCheck={false}
              placeholder="portal.yourschool.edu"
              aria-invalid={Boolean(customProblem)}
              className={customProblem ? "invalid" : undefined}
              onBlur={() => setCustomTouched(true)}
              onChange={(event) => onChange({ ...value, custom_domain: event.target.value })}
            />
            {customProblem ? (
              <p className="field-error">{customProblem}</p>
            ) : (
              <p className="field-hint">
                Your school account is created now. After registering you'll get two DNS records to add at your domain provider. The school
                website moves to your domain once they're verified; until then it's at {slug || "your-school"}.{root}.
              </p>
            )}
          </div>
        ) : null}
      </div>
    </fieldset>
  );
}
