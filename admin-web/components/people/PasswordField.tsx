"use client";

import { useState } from "react";

const ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";

/** A random 12-character password without look-alike characters (0/O, 1/l/I). */
export function generatePassword(length = 12): string {
  const bytes = new Uint32Array(length);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (n) => ALPHABET[n % ALPHABET.length]).join("");
}

/**
 * Sign-in password for a new account, with Show, Generate and Copy. The value only lives in
 * the form until it's submitted; the admin copies it to hand over to the person.
 */
export function PasswordField({
  id,
  label,
  value,
  onChange,
  error,
  hint,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  hint: string;
}) {
  const [visible, setVisible] = useState(false);
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setVisible(true); // clipboard blocked: show it so it can be copied by hand
    }
  }

  return (
    <div className="form-field">
      <label htmlFor={id}>{label} *</label>
      <div className="people-password">
        <input
          id={id}
          type={visible ? "text" : "password"}
          autoComplete="new-password"
          maxLength={128}
          value={value}
          className={error ? "invalid" : undefined}
          aria-invalid={Boolean(error)}
          aria-describedby={`${id}-hint`}
          onChange={(event) => onChange(event.target.value)}
        />
        <button className="link-btn" type="button" onClick={() => setVisible((v) => !v)}>
          {visible ? "Hide" : "Show"}
        </button>
        <button
          className="link-btn"
          type="button"
          onClick={() => {
            onChange(generatePassword());
            setVisible(true);
          }}
        >
          Generate
        </button>
        <button className="link-btn" type="button" disabled={!value} onClick={() => void copy()}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {error ? (
        <p className="field-error" id={`${id}-hint`}>
          {error}
        </p>
      ) : (
        <p className="field-hint" id={`${id}-hint`}>
          {hint}
        </p>
      )}
    </div>
  );
}
