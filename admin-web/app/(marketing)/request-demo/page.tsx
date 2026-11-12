import type { Metadata } from "next";
import { PublicShell } from "@/components/marketing/PublicShell";
import { RequestDemoForm } from "@/components/marketing/RequestDemoForm";

export const metadata: Metadata = { title: "Request a demo — SchoolSarthi" };

export default function RequestDemoPage() {
  return (
    <PublicShell>
      <article className="panel-card legal-doc">
        <h1>Request a demo</h1>
        <p className="muted">Tell us about your school and we&apos;ll arrange a walkthrough of SchoolSarthi.</p>
        <RequestDemoForm />
      </article>
    </PublicShell>
  );
}
