import Link from "next/link";
import { IconLogoMark } from "@/lib/icons";
import { BRAND } from "@/lib/marketing/content";

export default function SiteFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="site-footer-rich">
      <div className="site-footer-grid">
        <div>
          <div className="site-brand" style={{ marginBottom: 12 }}>
            <span className="sidebar-logo" aria-hidden>
              <IconLogoMark width={20} height={20} />
            </span>
            <span>
              {BRAND.name}
              <small>{BRAND.tagline}</small>
            </span>
          </div>
          <p className="muted">{BRAND.description}</p>
        </div>

        <div>
          <h4>Product</h4>
          <a href="#features">Features</a>
          <a href="#pricing">Pricing</a>
          <a href="#product">Product tour</a>
          <Link href="/dashboard">Admin dashboard</Link>
        </div>

        <div>
          <h4>Company</h4>
          <a href="#about">About</a>
          <a href="#contact">Contact</a>
          <a href="#testimonials">Stories</a>
          <a href="#faq">FAQ</a>
        </div>

        <div>
          <h4>Support</h4>
          <a href="#faq">Help center</a>
          <a href="#how-it-works">Documentation</a>
          <a href="#contact">Contact support</a>
          <Link href="/login">Sign in</Link>
        </div>
      </div>

      <div className="site-footer-bottom">
        <span>
          © {year} {BRAND.name}. All rights reserved.
        </span>
        <div className="footer-legal">
          <a href="#contact">Privacy Policy</a>
          <a href="#contact">Terms & Conditions</a>
          <a href="#contact">Refund Policy</a>
        </div>
      </div>
    </footer>
  );
}
