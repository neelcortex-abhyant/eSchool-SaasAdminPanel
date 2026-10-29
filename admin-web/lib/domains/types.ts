/** Shapes for school domains and public school sites (see backend/docs/SCHOOL_DOMAINS_API_CONTRACT.md). */

export type DomainType = "default" | "custom";
export type DomainStatus = "not_started" | "pending" | "verified" | "failed";

/** What a public school site shows. Every field but the name may be missing. */
export type SchoolSite = {
  school_id: number;
  name: string;
  slug: string;
  tagline: string | null;
  logo: string | null;
  address: string | null;
  city: string | null;
  phone: string | null;
  email: string | null;
  theme_primary: string | null;
  theme_secondary: string | null;
  about: string | null;
  admissions_open: boolean;
  /** pending_approval until the platform approves the school; the site still shows. */
  status: "pending_approval" | "active" | "inactive";
  /** All setup steps done (approved, profile, classes, admins…). */
  setup_complete: boolean;
  custom_domain: string | null;
  domain_status: DomainStatus;
};

/** unchecked: the format is fine but nothing could check whether it's free (the server decides on submit). */
export type Availability = { slug: string; available: boolean; problem: string; suggestions: string[]; unchecked?: boolean };

export type DomainChoice = { type: "default"; slug: string } | { type: "custom"; custom_domain: string; slug: string };

export type DomainSettings = {
  slug: string;
  default_url: string;
  domain_type: DomainType;
  custom_domain: string | null;
  domain_status: DomainStatus;
  verification: { txt_name: string; txt_value: string; cname_name: string; cname_target: string } | null;
  last_checked_at: string | null;
  last_error: string | null;
};
