"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo, useState } from "react";
import { NAV_ITEMS, SECONDARY_NAV, type NavChild, type NavItem } from "@/lib/nav";
import { IconChevron, IconLogoMark, IconSearch } from "@/lib/icons";

function isActivePath(pathname: string, href?: string) {
  if (!href) return false;
  if (href === "/dashboard" || href === "/school") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

function childMatches(child: NavChild, query: string): boolean {
  if (child.label.toLowerCase().includes(query)) return true;
  return child.children?.some((item) => childMatches(item, query)) ?? false;
}

function branchActive(pathname: string, children: NavChild[]): boolean {
  return children.some((child) => isActivePath(pathname, child.href) || (child.children ? branchActive(pathname, child.children) : false));
}

function itemMatches(pathname: string, item: NavItem, query: string) {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  if (item.label.toLowerCase().includes(q)) return true;
  return item.children?.some((child) => childMatches(child, q)) ?? false;
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
          if (item.note && !item.href && !item.children?.length) {
            const open = openGroups[item.label] ?? false;
            return (
              <div key={item.label}>
                <button
                  type="button"
                  className="sidebar-link"
                  onClick={() => toggleGroup(item.label)}
                  aria-expanded={open}
                >
                  <Icon />
                  <span className="sidebar-label">{item.label}</span>
                  <IconChevron className={`sidebar-chevron ${open ? "is-open" : ""}`} width={16} height={16} />
                </button>
                {open ? <p className="sidebar-note">{item.note}</p> : null}
              </div>
            );
          }

          if (item.children?.length) {
            const childActive = branchActive(pathname, item.children);
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
                  <NavChildren
                    items={item.children}
                    pathname={pathname}
                    query={query.trim().toLowerCase()}
                    openGroups={openGroups}
                    onToggle={toggleGroup}
                    onNavigate={onNavigate}
                  />
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

function NavChildren({
  items,
  pathname,
  query,
  openGroups,
  onToggle,
  onNavigate,
}: {
  items: NavChild[];
  pathname: string;
  query: string;
  openGroups: Record<string, boolean>;
  onToggle: (label: string) => void;
  onNavigate?: () => void;
}) {
  const visible = query ? items.filter((item) => childMatches(item, query)) : items;
  return (
    <div className="sidebar-children">
      {visible.map((child) => {
        if (child.children?.length) {
          const active = branchActive(pathname, child.children);
          const open = openGroups[child.label] ?? (active || Boolean(query));
          return (
            <div key={child.label}>
              <button
                type="button"
                className={`sidebar-child sidebar-group ${active ? "is-active" : ""}`}
                onClick={() => onToggle(child.label)}
                aria-expanded={open}
              >
                {child.label}
              </button>
              {open ? (
                <NavChildren
                  items={child.children}
                  pathname={pathname}
                  query={query}
                  openGroups={openGroups}
                  onToggle={onToggle}
                  onNavigate={onNavigate}
                />
              ) : null}
            </div>
          );
        }
        return (
          <Link
            key={child.href || child.label}
            href={child.href || "/school"}
            className={`sidebar-child ${isActivePath(pathname, child.href) ? "is-active" : ""}`}
            onClick={onNavigate}
          >
            {child.label}
          </Link>
        );
      })}
    </div>
  );
}
