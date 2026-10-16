import type { Metadata } from "next";
import Link from "next/link";
import RegisterSchoolForm from "@/components/marketing/RegisterSchoolForm";
import { IconBuilding, IconLogoMark } from "@/lib/icons";
import { BRAND } from "@/lib/marketing/content";

export const metadata: Metadata = {
  title: "Register your school — SchoolSarthi",
  description: "Register your institution to get started with school management.",
};

export default function RegisterSchoolPage() {
  return (
    <div className="site">
      <header className="site-header is-scrolled">
        <div className="site-header-inner">
          <Link href="/" className="site-brand">
            <span className="sidebar-logo" aria-hidden>
              <IconLogoMark width={22} height={22} />
            </span>
            <span>
              {BRAND.name}
              <small>{BRAND.tagline}</small>
            </span>
          </Link>
          <div className="site-actions">
            <Link href="/login" className="btn-pill btn-pill-green-soft">
              Login
            </Link>
          </div>
        </div>
      </header>
      <main className="register-page">
        <div className="register-intro">
          <p className="site-kicker">
            <IconBuilding width={16} height={16} /> Register your school
          </p>
          <h1>Register Your School</h1>
          <p>Bring your school management online. Register your institution to get started.</p>
        </div>
        <RegisterSchoolForm />
      </main>
    </div>
  );
}
