import Link from "next/link";
import type { ReactNode } from "react";
import { IconLogoMark } from "@/lib/icons";
import { BRAND } from "@/lib/marketing/content";

/** Header and centred column for the public pages (legal, request demo). Open to everyone. */
export function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="site">
      <header className="site-header is-scrolled">
        <div className="site-header-inner">
          <Link href="/" className="site-brand">
            <span className="sidebar-logo" aria-hidden>
              <IconLogoMark width={22} height={22} />
            </span>
            <span>
              {BRAND.name}
              <small>{BRAND.tagline}</small>
            </span>
          </Link>
          <div className="site-actions">
            <Link href="/login" className="btn-pill btn-pill-green-soft">
              Login
            </Link>
          </div>
        </div>
      </header>
      <main className="legal-page">{children}</main>
    </div>
  );
}
