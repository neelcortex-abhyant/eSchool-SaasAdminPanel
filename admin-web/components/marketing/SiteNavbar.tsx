"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { IconChevron, IconGlobe, IconLogoMark, IconMenu } from "@/lib/icons";
import { BRAND, NAV_LINKS, RESOURCE_LINKS } from "@/lib/marketing/content";
import { LANGUAGE_KEY } from "@/lib/workspace";

export default function SiteNavbar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [resourcesOpen, setResourcesOpen] = useState(false);
  const [languageOpen, setLanguageOpen] = useState(false);
  const [languages, setLanguages] = useState<{ code: string; name: string }[]>([{ code: "en", name: "English" }]);
  const [language, setLanguage] = useState("en");
  const [scrolled, setScrolled] = useState(false);
  const languageRef = useRef<HTMLDivElement>(null);
  const languageLabel = (languages.find((item) => item.code === language)?.code || language || "en").toUpperCase();

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 8);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    const stored = window.localStorage.getItem(LANGUAGE_KEY) || "en";
    setLanguage(stored);
    document.documentElement.lang = stored;
    let cancelled = false;
    fetch("/api/languages")
      .then((response) => response.json().catch(() => ({ data: [] })))
      .then((payload) => {
        if (cancelled) return;
        const rows = Array.isArray(payload?.data) ? payload.data : [];
        if (rows.length) {
          setLanguages(rows.map((row: { code?: string; name?: string }) => ({ code: row.code || "en", name: row.name || "English" })));
        }
      })
      .catch(() => undefined);
    function onDocClick(event: MouseEvent) {
      if (!languageRef.current?.contains(event.target as Node)) setLanguageOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => {
      cancelled = true;
      window.removeEventListener("scroll", onScroll);
      document.removeEventListener("mousedown", onDocClick);
    };
  }, []);

  function chooseLanguage(code: string) {
    setLanguage(code);
    window.localStorage.setItem(LANGUAGE_KEY, code);
    document.documentElement.lang = code;
    setLanguageOpen(false);
  }

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
          <div className="language-switch" ref={languageRef}>
            <button type="button" className="lang-pill" aria-label="Language" aria-expanded={languageOpen} onClick={() => setLanguageOpen((value) => !value)}>
              <IconGlobe width={15} height={15} />
              <span>{languageLabel}</span>
            </button>
            {languageOpen ? (
              <div className="dropdown-panel" role="menu">
                {languages.map((item) => (
                  <button key={item.code} type="button" className="dropdown-item" aria-current={item.code === language ? "true" : undefined} onClick={() => chooseLanguage(item.code)}>
                    {item.name}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
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
        {languages.map((item) => (
          <button key={item.code} type="button" onClick={() => { chooseLanguage(item.code); setMenuOpen(false); }}>
            {item.name}
          </button>
        ))}
        <Link href="/login" className="btn-pill btn-pill-green" onClick={() => setMenuOpen(false)}>
          Login / Get started
        </Link>
      </div>
    </header>
  );
}
