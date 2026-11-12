/**
 * Refund Policy shown at /refund-policy (linked from the site footer).
 * The approved wording hasn't been supplied, so no refund terms are published here. Put the
 * approved text in REFUND_POLICY.sections and set it as published; until then the page says the
 * policy will be published soon and points to Contact.
 */
import type { LegalDoc } from "@/lib/marketing/legal";

export const REFUND_POLICY_PUBLISHED = false;

export const REFUND_POLICY: LegalDoc = {
  title: "Refund Policy",
  intro: "Our refund policy will be published here soon. If you have a question about a payment or a refund in the meantime, please contact us.",
  sections: [],
};
