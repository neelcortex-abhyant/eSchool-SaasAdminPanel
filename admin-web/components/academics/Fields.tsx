"use client";

import type { ReactNode } from "react";

type Base = {
  id: string;
  label: string;
  required?: boolean;
  error?: string;
  hint?: string;
  span?: boolean;
};

function Wrapper({ id, label, required, error, hint, span, children }: Base & { children: ReactNode }) {
  return (
    <div className={`form-field${span ? " field-span" : ""}`}>
      <label htmlFor={id}>
        {label}
        {required ? " *" : ""}
      </label>
      {children}
      {error ? (
        <p className="field-error" id={`${id}-error`}>
          {error}
        </p>
      ) : hint ? (
        <p className="field-hint">{hint}</p>
      ) : null}
    </div>
  );
}

export function TextField({
  value,
  onChange,
  type = "text",
  placeholder,
  maxLength,
  disabled,
  min,
  max,
  autoComplete,
  ...base
}: Base & {
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "date" | "email" | "tel" | "number" | "password" | "time" | "datetime-local" | "url";
  placeholder?: string;
  maxLength?: number;
  disabled?: boolean;
  min?: string;
  max?: string;
  autoComplete?: string;
}) {
  return (
    <Wrapper {...base}>
      <input
        id={base.id}
        type={type}
        value={value}
        placeholder={placeholder}
        maxLength={maxLength}
        disabled={disabled}
        min={min}
        max={max}
        autoComplete={autoComplete}
        required={base.required}
        className={base.error ? "invalid" : undefined}
        aria-invalid={Boolean(base.error)}
        aria-describedby={base.error ? `${base.id}-error` : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
    </Wrapper>
  );
}

export function TextAreaField({
  value,
  onChange,
  placeholder,
  maxLength,
  rows = 3,
  ...base
}: Base & { value: string; onChange: (value: string) => void; placeholder?: string; maxLength?: number; rows?: number }) {
  return (
    <Wrapper {...base}>
      <textarea
        id={base.id}
        value={value}
        rows={rows}
        placeholder={placeholder}
        maxLength={maxLength}
        required={base.required}
        className={base.error ? "invalid" : undefined}
        aria-invalid={Boolean(base.error)}
        aria-describedby={base.error ? `${base.id}-error` : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
    </Wrapper>
  );
}

export type Option = { value: string; label: string; disabled?: boolean };

export function SelectField({
  value,
  onChange,
  options,
  placeholder,
  disabled,
  loading,
  ...base
}: Base & {
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  placeholder?: string;
  disabled?: boolean;
  loading?: boolean;
}) {
  return (
    <Wrapper {...base}>
      <select
        id={base.id}
        value={value}
        disabled={disabled || loading}
        required={base.required}
        className={base.error ? "invalid" : undefined}
        aria-invalid={Boolean(base.error)}
        aria-describedby={base.error ? `${base.id}-error` : undefined}
        onChange={(event) => onChange(event.target.value)}
      >
        {placeholder !== undefined ? <option value="">{loading ? "Loading…" : placeholder}</option> : null}
        {options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
      </select>
    </Wrapper>
  );
}

export function StatusToggle({ id, checked, onChange, label = "Active" }: { id: string; checked: boolean; onChange: (checked: boolean) => void; label?: string }) {
  return (
    <label className="acad-check" htmlFor={id}>
      <input id={id} type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}
