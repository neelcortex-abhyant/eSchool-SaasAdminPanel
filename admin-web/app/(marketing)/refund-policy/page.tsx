import type { Metadata } from "next";
import { LegalPage } from "@/components/marketing/LegalPage";
import { REFUND_POLICY, REFUND_POLICY_PUBLISHED } from "@/lib/marketing/refund";

export const metadata: Metadata = { title: "Refund Policy — SchoolSarthi" };

export default function RefundPolicyPage() {
  return <LegalPage doc={REFUND_POLICY} other={{ href: "/terms", label: "Terms and Conditions" }} pending={!REFUND_POLICY_PUBLISHED} />;
}
