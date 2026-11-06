import type { Metadata } from "next";
import { LegalPage } from "@/components/marketing/LegalPage";
import { PRIVACY } from "@/lib/marketing/legal";

export const metadata: Metadata = { title: "Privacy Policy — SchoolSarthi" };

export default function PrivacyPage() {
  return <LegalPage doc={PRIVACY} other={{ href: "/terms", label: "Terms and Conditions" }} />;
}
