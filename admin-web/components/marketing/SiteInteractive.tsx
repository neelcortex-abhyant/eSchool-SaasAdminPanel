"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { IconCheck, IconPlus } from "@/lib/icons";
import { CONTACT, FAQS, PLANS } from "@/lib/marketing/content";

// The landing sections that hold state. Everything else on the page renders on the server.
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
