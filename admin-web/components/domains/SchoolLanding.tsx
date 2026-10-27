import type { CSSProperties } from "react";
import { SetupIsland } from "@/components/domains/SetupIsland";
import { siteTheme, setupIncomplete } from "@/lib/domains/theme";
import type { SchoolSite } from "@/lib/domains/types";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter((word) => /^[A-Za-z0-9]/.test(word))
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join("");
}

/**
 * A school's public website: hero, About, Admissions, Contact and Login. Server-rendered, no
 * client libraries; only the admin's "Finish setup" link is a small client island.
 */
export function SchoolLanding({ site, loginUrl, appUrl }: { site: SchoolSite; loginUrl: string; appUrl: string }) {
  const theme = siteTheme(site.theme_primary, site.theme_secondary);
  const style = { "--site-primary": theme.primary, "--site-on-primary": theme.onPrimary, "--site-secondary": theme.secondary, "--site-on-secondary": theme.onSecondary } as CSSProperties;
  const location = [site.address, site.city].filter(Boolean).join(", ");
  const incomplete = setupIncomplete(site);
  const mapUrl = location ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${site.name}, ${location}`)}` : null;
  const phoneHref = site.phone ? `tel:${site.phone.replace(/[^\d+]/g, "")}` : null;
  const year = new Date().getFullYear();

  return (
    <div className="school-site" style={style}>
      <header className="ss-header">
        <a className="ss-brand" href="#top">
          {site.logo ? <img src={site.logo} alt="" width={40} height={40} /> : <span className="ss-monogram" aria-hidden>{initials(site.name) || "S"}</span>}
          <span>{site.name}</span>
        </a>
        <nav className="ss-nav" aria-label="Sections">
          <a href="#about">About</a>
          <a href="#admissions">Admissions</a>
          <a href="#contact">Contact</a>
          <a className="ss-btn ss-btn-primary" href={loginUrl}>
            Login
          </a>
        </nav>
      </header>

      {incomplete ? (
        <div className="ss-setup" role="status">
          <span>Our online portal is being set up. Some details may be added soon — you can still reach us using the contact details below.</span>
          <SetupIsland schoolId={site.school_id} appUrl={appUrl} />
        </div>
      ) : (
        <SetupIsland schoolId={site.school_id} appUrl={appUrl} compact />
      )}

      <main id="top">
        <section className="ss-hero">
          <div className="ss-hero-inner">
            {site.logo ? <img className="ss-hero-logo" src={site.logo} alt={`${site.name} logo`} width={88} height={88} /> : null}
            <p className="ss-eyebrow">{location || "Welcome"}</p>
            <h1>Welcome to {site.name}</h1>
            <p className="ss-lead">{site.tagline || "A place to learn, grow and belong."}</p>
            <div className="ss-hero-actions">
              {site.admissions_open ? (
                <a className="ss-btn ss-btn-secondary" href="#admissions">
                  Admissions
                </a>
              ) : null}
              <a className="ss-btn ss-btn-ghost" href={loginUrl}>
                Parent & staff login
              </a>
            </div>
          </div>
        </section>

        <section id="about" className="ss-section">
          <h2>About us</h2>
          <p>
            {site.about ||
              `${site.name}${site.city ? ` in ${site.city}` : ""} welcomes students and families. More about our school, our programmes and our community will appear here soon.`}
          </p>
        </section>

        <section id="admissions" className="ss-section ss-band">
          <h2>Admissions & enrolment</h2>
          {site.admissions_open ? (
            <>
              <p>Admissions are open. Contact the school office to ask about seats, fees, documents and visiting the campus.</p>
              <div className="ss-hero-actions">
                {site.email ? (
                  <a className="ss-btn ss-btn-primary" href={`mailto:${site.email}?subject=${encodeURIComponent(`Admission enquiry – ${site.name}`)}`}>
                    Email an enquiry
                  </a>
                ) : null}
                {phoneHref ? (
                  <a className="ss-btn ss-btn-outline" href={phoneHref}>
                    Call the office
                  </a>
                ) : null}
              </div>
            </>
          ) : (
            <p>Admissions aren't open right now. Please check back later or contact the school office.</p>
          )}
        </section>

        <section id="contact" className="ss-section">
          <h2>Contact</h2>
          <dl className="ss-contact">
            <div>
              <dt>Address</dt>
              <dd>
                {location ? (
                  <>
                    {location}
                    {mapUrl ? (
                      <>
                        {" · "}
                        <a href={mapUrl} target="_blank" rel="noopener noreferrer">
                          Map
                        </a>
                      </>
                    ) : null}
                  </>
                ) : (
                  "Address coming soon"
                )}
              </dd>
            </div>
            <div>
              <dt>Phone</dt>
              <dd>{phoneHref ? <a href={phoneHref}>{site.phone}</a> : "Coming soon"}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{site.email ? <a href={`mailto:${site.email}`}>{site.email}</a> : "Coming soon"}</dd>
            </div>
          </dl>
        </section>
      </main>

      <footer className="ss-footer">
        <span>
          © {year} {site.name}
        </span>
        <a href={loginUrl}>Login</a>
      </footer>
    </div>
  );
}

/** Shown when no school uses this address (also used by the custom-domain route). */
export function SchoolNotFound({ host }: { host: string }) {
  return (
    <div className="school-site ss-missing">
      <main className="ss-section">
        <h1>School not found</h1>
        <p>
          No school website is set up at <strong>{host}</strong> yet. If you run this school, finish connecting the domain in the admin
          portal, or check the address for typos.
        </p>
      </main>
    </div>
  );
}

/**
 * Shown at a school's address until its public website can be loaded (the backend has no public
 * lookup route yet). Neutral and indexed by nobody; the school's admin can preview the real site.
 */
export function SiteBeingSetUp({ host, loginUrl }: { host: string; loginUrl: string }) {
  return (
    <div className="school-site ss-missing">
      <main className="ss-section">
        <h1>This school's website is being set up</h1>
        <p>
          The website at <strong>{host}</strong> will be available soon. Students, parents and staff can already sign in to the school portal.
        </p>
        <p className="ss-hero-actions">
          <a className="ss-btn ss-btn-primary" href={loginUrl}>
            Login
          </a>
        </p>
      </main>
    </div>
  );
}
