import type { ComponentType, SVGProps } from "react";
import {
  IconBell,
  IconBook,
  IconBuilding,
  IconCalendar,
  IconChart,
  IconClasses,
  IconExam,
  IconFees,
  IconPackage,
  IconSettings,
  IconStaff,
  IconSupport,
  IconTeacher,
  IconUsers,
} from "@/lib/icons";

export type IconComp = ComponentType<SVGProps<SVGSVGElement>>;

export const BRAND = {
  name: "SchoolSarthi",
  tagline: "SaaS Platform",
  description:
    "A modern school management platform for institutions that want academics, people, and operations in one place.",
};

export const NAV_LINKS = [
  { href: "#home", label: "Home" },
  { href: "#features", label: "Features" },
  { href: "#about", label: "About" },
  { href: "#pricing", label: "Pricing" },
  { href: "#faq", label: "FAQ" },
  { href: "#contact", label: "Contact" },
] as const;

export const RESOURCE_LINKS = [
  { href: "#how-it-works", label: "Getting started" },
  { href: "#roles", label: "For each role" },
  { href: "/login", label: "Admin console" },
] as const;

export const STATS = [
  { value: "10,000+", label: "Students managed" },
  { value: "500+", label: "Schools onboarded" },
  { value: "99.9%", label: "Platform availability" },
  { value: "24/7", label: "Support coverage" },
] as const;

export const FEATURES: { title: string; body: string; icon: IconComp }[] = [
  { title: "Student management", body: "Admissions, profiles, guardians, and class assignments in one roster.", icon: IconUsers },
  { title: "Teacher management", body: "Onboard educators, assign subjects, and keep staff records current.", icon: IconTeacher },
  { title: "Attendance tracking", body: "Daily attendance with clear status views for classes and staff.", icon: IconCalendar },
  { title: "Academic operations", body: "Classes, subjects, lessons, and session years without tool-switching.", icon: IconClasses },
  { title: "Timetable planning", body: "Organize periods and teacher schedules with a clean operational view.", icon: IconBook },
  { title: "Examinations", body: "Plan exams, publish results, and keep performance records accessible.", icon: IconExam },
  { title: "Fees & payments", body: "Fee plans, collection status, and finance visibility for administrators.", icon: IconFees },
  { title: "Assignments", body: "Create, review, and track submissions across classes.", icon: IconStaff },
  { title: "Communication", body: "Announcements and notices that reach the right audience quickly.", icon: IconBell },
  { title: "Transport oversight", body: "Routes, shifts, and transport-related operations when your school needs them.", icon: IconBuilding },
  { title: "Staff & roles", body: "Permission-aware access so every role sees the right tools.", icon: IconSettings },
  { title: "Reports & analytics", body: "Dashboards that surface adoption, academics, and operational trends.", icon: IconChart },
];

export const SHOWCASE = [
  {
    id: "ops",
    eyebrow: "Operations console",
    title: "A calm control center for every school day",
    body: "From roster changes to fee follow-ups, SchoolSarthi keeps the work that matters within reach.",
    bullets: ["Real-time operational overview", "Role-based navigation", "Secure signed-in sessions", "Mobile-friendly layouts"],
    image:
      "https://images.unsplash.com/photo-1553877522-43269d4ea809?auto=format&fit=crop&w=1200&q=80",
    reverse: false,
  },
  {
    id: "academics",
    eyebrow: "Academics",
    title: "Teaching workflows without the clutter",
    body: "Help teachers and admins stay aligned on classes, attendance, and assessments.",
    bullets: ["Class & subject structure", "Attendance workflows", "Exam readiness", "Clear student context"],
    image:
      "https://images.unsplash.com/photo-1509062522246-3755977927d7?auto=format&fit=crop&w=1200&q=80",
    reverse: true,
  },
] as const;

export const ROLES = [
  {
    title: "School admin",
    body: "Configure academics, people, fees, and school-wide settings from one workspace.",
    icon: IconBuilding,
    href: "/login",
  },
  {
    title: "Teachers",
    body: "Manage lessons, attendance, and assignments with less administrative friction.",
    icon: IconTeacher,
    href: "/login",
  },
  {
    title: "Students",
    body: "Access class materials, assignments, and results in a focused learning view.",
    icon: IconUsers,
    href: "/login",
  },
  {
    title: "Parents",
    body: "Stay informed on progress, attendance, and important school updates.",
    icon: IconSupport,
    href: "/login",
  },
] as const;

export const STEPS = [
  { step: "01", title: "Create your school", body: "Set up the institution profile and choose the modules you need." },
  { step: "02", title: "Configure academics", body: "Add session years, classes, subjects, and staff roles." },
  { step: "03", title: "Invite your people", body: "Bring in teachers, students, and guardians with clear access." },
  { step: "04", title: "Run day-to-day ops", body: "Attendance, fees, exams, and communication — all in flow." },
] as const;

export const BENEFITS = [
  "Easy to use",
  "Secure sessions",
  "Scalable for networks",
  "Fast cloud access",
  "Mobile friendly",
  "Role-based permissions",
  "Actionable analytics",
  "Automated workflows",
] as const;

export const PLANS = [
  {
    id: "basic",
    name: "Basic",
    monthly: 29,
    yearly: 290,
    blurb: "Essential tools for a single growing school.",
    features: ["Student management", "Attendance basics", "Announcements", "Basic reports"],
    popular: false,
  },
  {
    id: "pro",
    name: "Professional",
    monthly: 79,
    yearly: 790,
    blurb: "Full academic and finance operations for active campuses.",
    features: ["Everything in Basic", "Fees & expenses", "Exams & assignments", "Staff roles"],
    popular: true,
  },
  {
    id: "business",
    name: "Business",
    monthly: 149,
    yearly: 1490,
    blurb: "Advanced packaging and multi-school readiness.",
    features: ["Everything in Professional", "Package controls", "Priority onboarding", "Extended reporting"],
    popular: false,
  },
] as const;

export const FAQS = [
  {
    q: "What is SchoolSarthi?",
    a: "SchoolSarthi is a school management SaaS console for academics, people, fees, and day-to-day operations.",
  },
  {
    q: "Can I manage multiple schools?",
    a: "Yes. Platform operators can onboard multiple institutions and assign packages from a central console.",
  },
  {
    q: "Can students and parents use the platform?",
    a: "The admin console is for operators and school staff. Student/parent experiences can connect through your existing app channels.",
  },
  {
    q: "Is there a free trial?",
    a: "You can start from the login portal. Trial packaging can be enabled when billing is connected.",
  },
  {
    q: "Can I upgrade my plan later?",
    a: "Plan changes are designed to roll into the next billing cycle once subscription APIs are enabled.",
  },
  {
    q: "Is my data secure?",
    a: "Operator access uses signed-in sessions with Bearer authentication. Keep secrets on the server — never in the browser.",
  },
  {
    q: "Does it work on mobile?",
    a: "Yes. The marketing site and admin UI are responsive for tablet and phone viewports.",
  },
  {
    q: "Do you provide support?",
    a: "Use the contact form for rollout questions. Production support channels can be added as you launch.",
  },
] as const;

export const TESTIMONIALS = [
  {
    name: "Ananya Mehta",
    role: "School Administrator",
    org: "Northridge Academy",
    quote: "We finally have one place for attendance, fees, and announcements. The team actually uses it every day.",
    rating: 5,
  },
  {
    name: "Rahul Desai",
    role: "Principal",
    org: "Greenfield High",
    quote: "Setup was straightforward and the dashboard gives us a clear pulse on school operations.",
    rating: 5,
  },
  {
    name: "Sofia Alvarez",
    role: "Operations Lead",
    org: "Harbor Learning Network",
    quote: "Role-based access means teachers see teaching tools and admins stay focused on oversight.",
    rating: 4,
  },
] as const;

export const CONTACT = {
  email: "hello@schoolsarthi.app",
  phone: "+1 (555) 014-2288",
  address: "200 Market Street, Suite 400, San Francisco, CA",
  hours: "Mon–Fri, 9:00–18:00 IST",
};
