/**
 * Platform Terms and Privacy Policy, shown at /terms and /privacy (linked from registration and
 * the site footer). The backend has no platform-wide legal content route, so the text lives here.
 * It is a working draft: set LEGAL_DRAFT to false once the business has approved the wording.
 */
export const LEGAL_DRAFT = true;
export const LEGAL_UPDATED = "5 November 2026";

export type LegalSection = { heading: string; body: string[] };
export type LegalDoc = { title: string; intro: string; sections: LegalSection[] };

export const TERMS: LegalDoc = {
  title: "Terms and Conditions",
  intro:
    "These terms cover a school's use of SchoolSarthi, the school management platform, by the school and the people it invites (administrators, teachers, staff, students and parents).",
  sections: [
    {
      heading: "Accounts",
      body: [
        "A school registers with accurate details and is responsible for the accounts it creates for its staff, students and parents.",
        "Keep passwords private. Tell us straight away if you think an account has been used without permission.",
      ],
    },
    {
      heading: "Using the platform",
      body: [
        "Use SchoolSarthi only for running your school: admissions, academics, attendance, fees, communication and related work.",
        "Don't try to reach another school's data, disrupt the service, or upload anything unlawful or harmful.",
      ],
    },
    {
      heading: "School data",
      body: [
        "Your school owns the records it adds. We process them to provide the service, as described in the Privacy Policy.",
        "You are responsible for having the right to add the personal data you enter, including consent where the law requires it.",
      ],
    },
    {
      heading: "Subscriptions and payments",
      body: ["Plans, prices and renewal terms are shown when a plan is assigned. Fees collected from parents through the platform belong to the school."],
    },
    {
      heading: "Availability and changes",
      body: [
        "We work to keep the service available but can't promise it will never be interrupted.",
        "We may update these terms. We'll show the date of the latest version on this page.",
      ],
    },
    {
      heading: "Ending use",
      body: ["A school can stop using the platform at any time. We may suspend an account that breaks these terms."],
    },
  ],
};

export const PRIVACY: LegalDoc = {
  title: "Privacy Policy",
  intro: "This policy explains what personal data SchoolSarthi handles for schools and how it is protected.",
  sections: [
    {
      heading: "What we hold",
      body: [
        "Details a school enters about its students, parents, teachers and staff, such as names, contact details, class, attendance, marks, fees and documents.",
        "Account details (email, role, sign-in times) and messages sent through the platform.",
      ],
    },
    {
      heading: "Why we use it",
      body: [
        "Only to provide the school's services: running classes, records, fees, communication and reports, and keeping accounts secure.",
        "We don't sell personal data or use it for advertising.",
      ],
    },
    {
      heading: "Who can see it",
      body: [
        "Each school's data is kept separate. People see what their role allows: for example, parents see their own children's records.",
        "Service providers that host or deliver the platform (servers, email, notifications, payments) process data only on our instructions.",
      ],
    },
    {
      heading: "Keeping it safe",
      body: ["Data is sent over encrypted connections, and access is limited by sign-in and role. Files are only served to signed-in users with access."],
    },
    {
      heading: "How long we keep it",
      body: ["For as long as the school uses the platform, and afterwards only as long as the law requires or the school asks."],
    },
    {
      heading: "Your choices",
      body: [
        "Parents, students and staff can ask their school to see, correct or delete their data. The school handles the request through the platform.",
      ],
    },
  ],
};
