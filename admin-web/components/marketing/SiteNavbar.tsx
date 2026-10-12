"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { IconChevron, IconGlobe, IconLogoMark, IconMenu } from "@/lib/icons";
import { BRAND, NAV_LINKS, RESOURCE_LINKS } from "@/lib/marketing/content";

export default function SiteNavbar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [resourcesOpen, setResourcesOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 8);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`site-header ${scrolled ? "is-scrolled" : ""}`}>
      <div className="site-header-inner">
        <Link href="/#home" className="site-brand" onClick={() => setMenuOpen(false)}>
          <span className="sidebar-logo" aria-hidden>
            <IconLogoMark width={22} height={22} />
          </span>
          <span>
            {BRAND.name}
            <small>{BRAND.tagline}</small>
          </span>
        </Link>

        <nav className="site-nav" aria-label="Primary">
          {NAV_LINKS.map((item) => (
            <a key={item.href} href={item.href}>
              {item.label}
            </a>
          ))}
          <div className="site-dropdown">
            <button
              type="button"
              className="site-dropdown-trigger"
              aria-expanded={resourcesOpen}
              onClick={() => setResourcesOpen((v) => !v)}
            >
              Resources <IconChevron width={14} height={14} />
            </button>
            {resourcesOpen ? (
              <div className="site-dropdown-panel">
                {RESOURCE_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    onClick={() => setResourcesOpen(false)}
                  >
                    {link.label}
                  </Link>
                ))}
              </div>
            ) : null}
          </div>
        </nav>

        <div className="site-actions">
          <button type="button" className="lang-pill" aria-label="Language">
            <IconGlobe width={15} height={15} />
            <span>EN</span>
          </button>
          <Link href="/login" className="btn-pill btn-pill-green-soft">
            Login
          </Link>
          <Link href="/login" className="btn-pill btn-pill-green">
            Start free trial
          </Link>
          <button
            type="button"
            className="site-menu-btn"
            aria-label="Open menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
          >
            <IconMenu width={18} height={18} />
          </button>
        </div>
      </div>

      <div className={`site-mobile-nav ${menuOpen ? "is-open" : ""}`}>
        {NAV_LINKS.map((item) => (
          <a key={item.href} href={item.href} onClick={() => setMenuOpen(false)}>
            {item.label}
          </a>
        ))}
        {RESOURCE_LINKS.map((link) => (
          <Link key={link.href} href={link.href} onClick={() => setMenuOpen(false)}>
            {link.label}
          </Link>
        ))}
        <Link href="/login" className="btn-pill btn-pill-green" onClick={() => setMenuOpen(false)}>
          Login / Get started
        </Link>
      </div>
    </header>
  );
}
