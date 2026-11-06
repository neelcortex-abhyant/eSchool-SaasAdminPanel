"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export type TabLink = { href: string; label: string };

/** Section tabs that are links (one page per tab); the current path is marked active. */
export function LinkTabs({ tabs, label }: { tabs: TabLink[]; label: string }) {
  const pathname = usePathname();
  return (
    <nav className="acad-tabs" aria-label={label}>
      {tabs.map((tab) => (
        <Link key={tab.href} href={tab.href} className={`acad-tab${pathname === tab.href ? " is-active" : ""}`} aria-current={pathname === tab.href ? "page" : undefined}>
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}

/** Tabs that switch content on the same page. */
export function ButtonTabs<T extends string>({ tabs, value, onChange, label }: { tabs: { value: T; label: string }[]; value: T; onChange: (value: T) => void; label: string }) {
  return (
    <div className="acad-tabs rpt-tabs" role="tablist" aria-label={label}>
      {tabs.map((tab) => (
        <button key={tab.value} type="button" role="tab" aria-selected={tab.value === value} className={`acad-tab${tab.value === value ? " is-active" : ""}`} onClick={() => onChange(tab.value)}>
          {tab.label}
        </button>
      ))}
    </div>
  );
}
