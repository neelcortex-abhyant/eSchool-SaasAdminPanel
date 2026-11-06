import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

/**
 * The app's buttons. Variants map to the existing classes:
 * primary → amber pill, secondary → soft pill, danger → red pill, link → text button.
 */
export type ButtonVariant = "primary" | "secondary" | "danger" | "link" | "link-danger";

const CLASS: Record<ButtonVariant, string> = {
  primary: "btn-pill btn-pill-green",
  secondary: "btn-pill btn-pill-green-soft",
  danger: "btn-pill btn-pill-danger",
  link: "link-btn",
  "link-danger": "link-btn danger",
};

export function buttonClass(variant: ButtonVariant = "primary", extra?: string): string {
  return extra ? `${CLASS[variant]} ${extra}` : CLASS[variant];
}

export function Button({
  variant = "primary",
  busy = false,
  busyLabel,
  className,
  type = "button",
  disabled,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; busy?: boolean; busyLabel?: string; children: ReactNode }) {
  return (
    <button {...rest} type={type} className={buttonClass(variant, className)} disabled={disabled || busy} aria-busy={busy || undefined}>
      {busy && busyLabel ? busyLabel : children}
    </button>
  );
}

/** A link styled as a button, e.g. "Add school" in a page header. */
export function ButtonLink({ href, variant = "primary", className, children }: { href: string; variant?: ButtonVariant; className?: string; children: ReactNode }) {
  return (
    <Link href={href} className={buttonClass(variant, className)}>
      {children}
    </Link>
  );
}
