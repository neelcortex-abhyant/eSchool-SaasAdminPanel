import Link from "next/link";
import { IconLogoMark } from "@/lib/icons";
import { BRAND } from "@/lib/marketing/content";
import { LEGAL_DRAFT, LEGAL_UPDATED, type LegalDoc } from "@/lib/marketing/legal";

/** Public legal page (Terms, Privacy): the site header, the document and links between them. */
export function LegalPage({ doc, other }: { doc: LegalDoc; other: { href: string; label: string } }) {
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
      <main className="legal-page">
        <article className="panel-card legal-doc">
          <h1>{doc.title}</h1>
          <p className="muted">Last updated {LEGAL_UPDATED}</p>
          {LEGAL_DRAFT ? <p className="alert alert-info">This page is being finalised. Contact us if you have a question about it.</p> : null}
          <p>{doc.intro}</p>
          {doc.sections.map((section) => (
            <section key={section.heading}>
              <h2>{section.heading}</h2>
              {section.body.map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
            </section>
          ))}
          <p className="legal-links">
            <Link href={other.href}>{other.label}</Link> · <Link href="/#contact">Contact</Link> · <Link href="/register-school">Register your school</Link>
          </p>
        </article>
      </main>
    </div>
  );
}
