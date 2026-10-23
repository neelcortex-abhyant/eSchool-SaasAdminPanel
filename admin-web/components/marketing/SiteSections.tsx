import Image from "next/image";
import Link from "next/link";
import { IconCheck } from "@/lib/icons";
import { BENEFITS, FEATURES, ROLES, SHOWCASE, STATS, STEPS, TESTIMONIALS } from "@/lib/marketing/content";

export { ContactSection, FAQSection, PricingSection } from "@/components/marketing/SiteInteractive";
export function StatsSection() {
  return (
    <section className="stats-strip" aria-label="Platform statistics">
      {STATS.map((stat, index) => (
        <div key={stat.label} className="stats-item">
          {index > 0 ? <span className="stats-sep" aria-hidden /> : null}
          <div>
            <strong>{stat.value}</strong>
            <span>{stat.label}</span>
          </div>
        </div>
      ))}
    </section>
  );
}

export function FeaturesSection() {
  return (
    <section className="site-section" id="features">
      <div className="site-section-head">
        <h2>Everything you need to manage your school</h2>
        <p>
          A complete toolkit for academics, people, finance, and communication —
          presented in a clean, operator-friendly interface.
        </p>
      </div>
      <div className="feature-grid dense">
        {FEATURES.map((feature) => {
          const Icon = feature.icon;
          return (
            <article key={feature.title} className="feature-card">
              <div className="feature-icon">
                <Icon width={20} height={20} />
              </div>
              <h3>{feature.title}</h3>
              <p>{feature.body}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function ShowcaseSection() {
  return (
    <section className="site-section" id="product">
      <div className="site-section-head">
        <h2>Powerful tools. Simple experience.</h2>
        <p>See how SchoolSarthi keeps school operations clear without overwhelming the team.</p>
      </div>
      <div className="showcase-stack">
        {SHOWCASE.map((block) => (
          <div
            key={block.id}
            className={`showcase-row ${block.reverse ? "is-reverse" : ""}`}
          >
            <div>
              <p className="site-kicker">{block.eyebrow}</p>
              <h3 className="showcase-title">{block.title}</h3>
              <p className="site-hero-copy">{block.body}</p>
              <ul className="check-list">
                {block.bullets.map((item) => (
                  <li key={item}>
                    <IconCheck width={16} height={16} />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div className="showcase-media">
              <Image
                src={block.image}
                alt=""
                width={1200}
                height={800}
                sizes="(max-width: 960px) 100vw, 576px"
                quality={70}
                className="showcase-image"
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function RolesSection() {
  return (
    <section className="site-section" id="roles">
      <div className="site-section-head">
        <h2>Built for every role in your school</h2>
        <p>Give each audience the right workspace without diluting control.</p>
      </div>
      <div className="feature-grid">
        {ROLES.map((role) => {
          const Icon = role.icon;
          return (
            <article key={role.title} className="feature-card role-card">
              <div className="feature-icon">
                <Icon width={20} height={20} />
              </div>
              <h3>{role.title}</h3>
              <p>{role.body}</p>
              <Link href={role.href} className="text-link">
                Explore console →
              </Link>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function HowItWorksSection() {
  return (
    <section className="site-section" id="how-it-works">
      <div className="site-section-head">
        <h2>How it works</h2>
        <p>A clear path from first setup to daily school operations.</p>
      </div>
      <div className="steps-row">
        {STEPS.map((step) => (
          <article key={step.step} className="step-card">
            <span className="step-num">{step.step}</span>
            <h3>{step.title}</h3>
            <p>{step.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

export function WhyChooseSection() {
  return (
    <section className="site-section why-section" id="about">
      <div className="why-grid">
        <div>
          <p className="site-kicker">Why SchoolSarthi</p>
          <h2>Built to make school management simpler</h2>
          <p className="site-hero-copy">
            SchoolSarthi is designed for long admin sessions: light surfaces, strong
            hierarchy, and green actions that make the next step obvious.
          </p>
          <Link href="/login" className="btn-pill btn-pill-green">
            Open admin console
          </Link>
        </div>
        <div className="benefit-grid">
          {BENEFITS.map((item) => (
            <div key={item} className="benefit-chip">
              <IconCheck width={16} height={16} />
              {item}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function TestimonialsSection() {
  return (
    <section className="site-section" id="testimonials">
      <div className="site-section-head">
        <h2>What school administrators are saying</h2>
        <p>Placeholder quotes you can replace with real customer stories.</p>
      </div>
      <div className="feature-grid">
        {TESTIMONIALS.map((item) => (
          <article key={item.name} className="feature-card testimonial-card">
            <div className="stars" aria-label={`${item.rating} out of 5 stars`}>
              {"★".repeat(item.rating)}
              {"☆".repeat(5 - item.rating)}
            </div>
            <p className="testimonial-quote">“{item.quote}”</p>
            <div className="testimonial-meta">
              <div className="user-avatar" aria-hidden>
                {item.name
                  .split(" ")
                  .map((p) => p[0])
                  .join("")}
              </div>
              <div>
                <strong>{item.name}</strong>
                <div className="muted">
                  {item.role} · {item.org}
                </div>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function CTASection() {
  return (
    <section className="cta-band">
      <div className="cta-band-inner">
        <h2>Ready to simplify your school management?</h2>
        <p>
          Bring academics, students, teachers, and administration together in one
          powerful platform.
        </p>
        <div className="site-cta-row" style={{ justifyContent: "center" }}>
          <Link href="/login" className="btn-pill btn-pill-green">
            Get started
          </Link>
          <Link href="/login" className="btn-pill btn-pill-light">
            Book a demo
          </Link>
        </div>
      </div>
    </section>
  );
}
