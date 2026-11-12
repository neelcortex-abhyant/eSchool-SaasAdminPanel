"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { TextAreaField, TextField } from "@/components/ui/Fields";
import { CONTACT } from "@/lib/marketing/content";
import { demoMailto, demoRequestProblems, EMPTY_DEMO_REQUEST, submitDemoRequest, type DemoOutcome, type DemoRequest } from "@/lib/marketing/demo";

/** Public demo request: works signed in or out, and says honestly whether the request was sent. */
export function RequestDemoForm() {
  const [values, setValues] = useState<DemoRequest>(EMPTY_DEMO_REQUEST);
  const [errors, setErrors] = useState<Partial<Record<keyof DemoRequest, string>>>({});
  const [pending, setPending] = useState(false);
  const [outcome, setOutcome] = useState<DemoOutcome | null>(null);

  function set(key: keyof DemoRequest, value: string) {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => {
      if (!current[key]) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const problems = demoRequestProblems(values);
    setErrors(problems);
    if (Object.keys(problems).length) return;
    setPending(true);
    setOutcome(null);
    const result = await submitDemoRequest(values);
    setPending(false);
    setOutcome(result);
    if (result.state === "sent") setValues(EMPTY_DEMO_REQUEST);
  }

  if (outcome?.state === "sent") {
    return (
      <div className="alert alert-success" role="status">
        <strong>Thanks, your demo request has been sent.</strong> We&apos;ll contact you to arrange a time.{" "}
        <Link href="/">Back to the home page</Link>
      </div>
    );
  }

  return (
    <form className="resource-form demo-form" onSubmit={onSubmit} noValidate>
      {outcome?.state === "unavailable" ? (
        <div className="alert alert-info field-span" role="status">
          Online demo requests aren&apos;t switched on yet, so this request wasn&apos;t sent.{" "}
          <a href={demoMailto(CONTACT.email, values)}>Email it to {CONTACT.email}</a> instead; your details are filled in.
        </div>
      ) : null}
      {outcome?.state === "failed" ? (
        <div className="alert alert-danger field-span" role="alert">
          {outcome.message}
        </div>
      ) : null}
      <TextField id="demo-name" label="Your name" required autoComplete="name" maxLength={120} value={values.name} onChange={(v) => set("name", v)} error={errors.name} />
      <TextField id="demo-school" label="School name" required autoComplete="organization" maxLength={255} value={values.school_name} onChange={(v) => set("school_name", v)} error={errors.school_name} />
      <TextField id="demo-email" label="Email" type="email" required autoComplete="email" maxLength={255} value={values.email} onChange={(v) => set("email", v)} error={errors.email} />
      <TextField id="demo-phone" label="Phone" type="tel" required autoComplete="tel" maxLength={32} value={values.phone} onChange={(v) => set("phone", v)} error={errors.phone} />
      <TextField id="demo-city" label="City" autoComplete="address-level2" maxLength={120} value={values.city} onChange={(v) => set("city", v)} error={errors.city} />
      <TextField id="demo-students" label="Number of students" type="number" min="0" value={values.students} onChange={(v) => set("students", v)} error={errors.students} />
      <TextAreaField id="demo-message" label="What would you like to see?" span maxLength={1000} value={values.message} onChange={(v) => set("message", v)} error={errors.message} />
      <div className="field-span page-actions">
        <button className="btn-pill btn-pill-green" type="submit" disabled={pending}>
          {pending ? "Sending…" : "Request a demo"}
        </button>
      </div>
    </form>
  );
}
