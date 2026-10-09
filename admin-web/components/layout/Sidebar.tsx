"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo, useState } from "react";
import { NAV_ITEMS, SECONDARY_NAV, type NavItem } from "@/lib/nav";
import { IconChevron, IconLogoMark, IconSearch } from "@/lib/icons";

function isActivePath(pathname: string, href?: string) {
  if (!href) return false;
  if (href === "/dashboard") return pathname === "/dashboard";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function itemMatches(pathname: string, item: NavItem, query: string) {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  if (item.label.toLowerCase().includes(q)) return true;
  return item.children?.some((c) => c.label.toLowerCase().includes(q)) ?? false;
}

export default function Sidebar({
  collapsed,
  mobileOpen,
  onNavigate,
  navItems = NAV_ITEMS,
  secondaryItems = SECONDARY_NAV,
  subtitle = "Admin Panel",
}: {
  collapsed: boolean;
  mobileOpen: boolean;
  onNavigate?: () => void;
  navItems?: NavItem[];
  secondaryItems?: NavItem[];
  subtitle?: string;
}) {
  const pathname = usePathname();
  const [query, setQuery] = useState("");
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});

  const items = useMemo(() => {
    const primary = navItems.filter((item) => itemMatches(pathname, item, query));
    const secondary = query
      ? secondaryItems.filter((item) => itemMatches(pathname, item, query))
      : secondaryItems.slice(0, 3);
    return [...primary, ...secondary];
  }, [pathname, query, navItems, secondaryItems]);

  function toggleGroup(label: string) {
    setOpenGroups((prev) => ({ ...prev, [label]: !prev[label] }));
  }

  return (
    <aside className="admin-sidebar" aria-label="Main navigation">
      <div className="sidebar-brand">
        <div className="sidebar-logo" aria-hidden>
          <IconLogoMark width={22} height={22} />
        </div>
        <div className="sidebar-brand-text">
          <div className="sidebar-brand-name">SchoolSarthi</div>
          <div className="sidebar-brand-sub">{subtitle}</div>
        </div>
      </div>

      <div className="sidebar-search">
        <span className="sidebar-search-icon">
          <IconSearch width={16} height={16} />
        </span>
        <input
          type="search"
          placeholder="Search menu…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search menu"
        />
      </div>

      <nav className="sidebar-nav">
        {items.map((item) => {
          const Icon = item.icon;
          if (item.children?.length) {
            const childActive = item.children.some((c) => isActivePath(pathname, c.href));
            const open = openGroups[item.label] ?? (childActive || Boolean(query));
            return (
              <div key={item.label}>
                <button
                  type="button"
                  className={`sidebar-link ${childActive ? "is-active" : ""}`}
                  onClick={() => toggleGroup(item.label)}
                  aria-expanded={open}
                >
                  <Icon />
                  <span className="sidebar-label">{item.label}</span>
                  <IconChevron className={`sidebar-chevron ${open ? "is-open" : ""}`} width={16} height={16} />
                </button>
                {open ? (
                  <div className="sidebar-children">
                    {item.children.map((child) => (
                      <Link
                        key={child.href}
                        href={child.href}
                        className={`sidebar-child ${isActivePath(pathname, child.href) ? "is-active" : ""}`}
                        onClick={onNavigate}
                      >
                        {child.label}
                      </Link>
                    ))}
                  </div>
                ) : null}
              </div>
            );
          }

          return (
            <Link
              key={`${item.label}-${item.href}`}
              href={item.href || "/"}
              className={`sidebar-link ${isActivePath(pathname, item.href) ? "is-active" : ""}`}
              onClick={onNavigate}
              title={collapsed ? item.label : undefined}
            >
              <Icon />
              <span className="sidebar-label">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {!mobileOpen ? null : null}
    </aside>
  );
}
