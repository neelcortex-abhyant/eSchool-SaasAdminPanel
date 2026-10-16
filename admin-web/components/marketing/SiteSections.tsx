"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { IconCheck, IconPlus } from "@/lib/icons";
import {
  BENEFITS,
  CONTACT,
  FAQS,
  FEATURES,
  PLANS,
  ROLES,
  SHOWCASE,
  STATS,
  STEPS,
  TESTIMONIALS,
} from "@/lib/marketing/content";

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

export function PricingSection() {
  const [yearly, setYearly] = useState(false);

  return (
    <section className="site-section" id="pricing">
      <div className="site-section-head">
        <h2>Simple pricing that scales with your school</h2>
        <p>Sample plans for the marketing surface. Connect live billing when ready.</p>
        <div className="billing-toggle" role="group" aria-label="Billing period">
          <button
            type="button"
            className={!yearly ? "is-active" : ""}
            onClick={() => setYearly(false)}
          >
            Monthly
          </button>
          <button
            type="button"
            className={yearly ? "is-active" : ""}
            onClick={() => setYearly(true)}
          >
            Yearly
          </button>
        </div>
      </div>
      <div className="pricing-grid">
        {PLANS.map((plan) => {
          const price = yearly ? plan.yearly : plan.monthly;
          return (
            <article
              key={plan.id}
              className={`price-card ${plan.popular ? "is-featured" : ""}`}
            >
              {plan.popular ? <span className="popular-badge">Most popular</span> : null}
              <h3>{plan.name}</h3>
              <div className="price-amount">
                ${price}
                <small>/{yearly ? "year" : "month"}</small>
              </div>
              <p className="muted">{plan.blurb}</p>
              <ul>
                {plan.features.map((feature) => (
                  <li key={feature}>{feature}</li>
                ))}
              </ul>
              <Link
                href="/login"
                className={`btn-pill ${plan.popular ? "btn-pill-green" : "btn-pill-green-soft"}`}
                style={{ width: "100%" }}
              >
                Get started
              </Link>
            </article>
          );
        })}
        <article className="price-card">
          <h3>Enterprise</h3>
          <div className="price-amount">Custom</div>
          <p className="muted">For networks that need tailored packaging and support.</p>
          <ul>
            <li>Multi-school controls</li>
            <li>Custom onboarding</li>
            <li>Dedicated success contact</li>
            <li>Security review support</li>
          </ul>
          <Link href="#contact" className="btn-pill btn-pill-green-soft" style={{ width: "100%" }}>
            Talk to us
          </Link>
        </article>
      </div>
    </section>
  );
}

export function FAQSection() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <section className="site-section" id="faq">
      <div className="site-section-head">
        <h2>Frequently asked questions</h2>
        <p>Quick answers for operators evaluating SchoolSarthi.</p>
      </div>
      <div className="faq-list">
        {FAQS.map((item, index) => {
          const isOpen = open === index;
          return (
            <div key={item.q} className={`faq-item ${isOpen ? "is-open" : ""}`}>
              <button
                type="button"
                className="faq-trigger"
                aria-expanded={isOpen}
                onClick={() => setOpen(isOpen ? null : index)}
              >
                <span>{item.q}</span>
                <IconPlus
                  width={18}
                  height={18}
                  style={{ transform: isOpen ? "rotate(45deg)" : undefined }}
                />
              </button>
              {isOpen ? <p className="faq-answer">{item.a}</p> : null}
            </div>
          );
        })}
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

export function ContactSection() {
  const [pending, setPending] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    name: "",
    email: "",
    phone: "",
    subject: "",
    message: "",
  });

  const canSubmit = useMemo(
    () =>
      form.name.trim().length > 1 &&
      /\S+@\S+\.\S+/.test(form.email) &&
      form.message.trim().length > 5,
    [form],
  );

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (!canSubmit) {
      setError("Please fill name, a valid email, and a short message.");
      return;
    }
    setPending(true);
    // No contact API in this project yet — keep UX complete without breaking builds.
    await new Promise((resolve) => setTimeout(resolve, 700));
    setPending(false);
    setSuccess("Thanks — your message is ready to send when a contact API is connected.");
    setForm({ name: "", email: "", phone: "", subject: "", message: "" });
  }

  return (
    <section className="site-section" id="contact">
      <div className="contact-grid">
        <div>
          <p className="site-kicker">Contact</p>
          <h2>Let’s talk</h2>
          <p className="site-hero-copy">
            Questions about rollout, packaging, or demos — we would love to hear from you.
          </p>
          <ul className="contact-list">
            <li>
              <strong>Email</strong>
              <span>{CONTACT.email}</span>
            </li>
            <li>
              <strong>Phone</strong>
              <span>{CONTACT.phone}</span>
            </li>
            <li>
              <strong>Address</strong>
              <span>{CONTACT.address}</span>
            </li>
            <li>
              <strong>Support hours</strong>
              <span>{CONTACT.hours}</span>
            </li>
          </ul>
        </div>

        <form className="contact-form" onSubmit={onSubmit} noValidate>
          {error ? <div className="alert alert-danger">{error}</div> : null}
          {success ? <div className="alert alert-info">{success}</div> : null}
          <div className="form-field">
            <label htmlFor="contact-name">Name</label>
            <input
              id="contact-name"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              required
            />
          </div>
          <div className="form-grid-2">
            <div className="form-field">
              <label htmlFor="contact-email">Email</label>
              <input
                id="contact-email"
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                required
              />
            </div>
            <div className="form-field">
              <label htmlFor="contact-phone">Phone</label>
              <input
                id="contact-phone"
                value={form.phone}
                onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
              />
            </div>
          </div>
          <div className="form-field">
            <label htmlFor="contact-subject">Subject</label>
            <input
              id="contact-subject"
              value={form.subject}
              onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
            />
          </div>
          <div className="form-field">
            <label htmlFor="contact-message">Message</label>
            <textarea
              id="contact-message"
              rows={5}
              value={form.message}
              onChange={(e) => setForm((f) => ({ ...f, message: e.target.value }))}
              required
            />
          </div>
          <button className="btn-pill btn-pill-green" type="submit" disabled={pending}>
            {pending ? "Sending…" : "Send message"}
          </button>
        </form>
      </div>
    </section>
  );
}
