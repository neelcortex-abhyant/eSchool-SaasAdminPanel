import type { Metadata } from "next";
import { LegalPage } from "@/components/marketing/LegalPage";
import { TERMS } from "@/lib/marketing/legal";

export const metadata: Metadata = { title: "Terms and Conditions — SchoolSarthi" };

export default function TermsPage() {
  return <LegalPage doc={TERMS} other={{ href: "/privacy", label: "Privacy Policy" }} />;
}
