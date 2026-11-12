import Link from "next/link";
import { PublicShell } from "@/components/marketing/PublicShell";
import { LEGAL_DRAFT, LEGAL_UPDATED, type LegalDoc } from "@/lib/marketing/legal";

/** Public legal page (Terms, Privacy): the site header, the document and links between them. */
/** `pending`: no approved text yet, so the page shows no date or draft note, only the intro. */
export function LegalPage({ doc, other, pending = false }: { doc: LegalDoc; other: { href: string; label: string }; pending?: boolean }) {
  return (
    <PublicShell>
      <article className="panel-card legal-doc">
        <h1>{doc.title}</h1>
        {pending ? null : <p className="muted">Last updated {LEGAL_UPDATED}</p>}
        {LEGAL_DRAFT && !pending ? <p className="alert alert-info">This page is being finalised. Contact us if you have a question about it.</p> : null}
        <p className={pending ? "alert alert-info" : undefined}>{doc.intro}</p>
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
    </PublicShell>
  );
}
