"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, clearSession } from "@/lib/api";
import { IconBell, IconChevron, IconGlobe, IconMenu } from "@/lib/icons";

type HeaderUser = {
  first_name?: string;
  last_name?: string;
  email?: string;
};

export default function TopHeader({
  user,
  onToggleSidebar,
}: {
  user: HeaderUser | null;
  onToggleSidebar: () => void;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const displayName =
    [user?.first_name, user?.last_name].filter(Boolean).join(" ") ||
    user?.email ||
    "Admin";
  const initials = displayName
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() || "")
    .join("") || "A";

  useEffect(() => {
    function onDocClick(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {
      // Clear local session even if the network call fails.
    }
    clearSession();
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="admin-header">
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <button
          type="button"
          className="icon-btn"
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
        >
          <IconMenu width={20} height={20} />
        </button>
      </div>

      <div className="header-right">
        <button type="button" className="lang-pill" aria-label="Language">
          <IconGlobe width={16} height={16} />
          <span>EN</span>
        </button>

        <button type="button" className="icon-btn" aria-label="Notifications">
          <IconBell width={18} height={18} />
          <span className="badge-dot" />
        </button>

        <div className="user-menu-wrap" ref={menuRef}>
          <button
            type="button"
            className="user-trigger"
            onClick={() => setOpen((v) => !v)}
            aria-haspopup="menu"
            aria-expanded={open}
          >
            <span className="user-avatar">{initials}</span>
            <span className="user-name">{displayName}</span>
            <IconChevron width={14} height={14} />
          </button>

          {open ? (
            <div className="dropdown-panel" role="menu">
              <Link href="/settings" className="dropdown-item" onClick={() => setOpen(false)}>
                Profile
              </Link>
              <Link href="/settings" className="dropdown-item" onClick={() => setOpen(false)}>
                Account settings
              </Link>
              <Link href="/settings" className="dropdown-item" onClick={() => setOpen(false)}>
                Change password
              </Link>
              <button type="button" className="dropdown-item is-danger" onClick={logout}>
                Logout
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}
