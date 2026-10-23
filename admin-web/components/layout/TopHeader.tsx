"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { adminApi } from "@/lib/adminApi";
import { api, clearSession } from "@/lib/api";
import { IconBell, IconCalendar, IconChevron, IconGlobe, IconLogoMark, IconMenu } from "@/lib/icons";
import { LANGUAGE_KEY, THEME_KEY, readWorkspace, writeWorkspace } from "@/lib/workspace";

const SEEN_NOTICES_KEY = "header-notices-seen";

type HeaderNotice = {
  id: string;
  title: string;
  detail: string;
};

type HeaderUser = {
  first_name?: string;
  last_name?: string;
  email?: string;
  role?: string;
};

function readSeenNotices(): string[] {
  try {
    const raw = JSON.parse(window.localStorage.getItem(SEEN_NOTICES_KEY) || "[]");
    return Array.isArray(raw) ? raw.map(String) : [];
  } catch {
    return [];
  }
}

export default function TopHeader({
  user,
  onToggleSidebar,
  schoolName,
}: {
  user: HeaderUser | null;
  onToggleSidebar: () => void;
  schoolName?: string | null;
  schoolCode?: string | null;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [languageOpen, setLanguageOpen] = useState(false);
  const [noticeOpen, setNoticeOpen] = useState(false);
  const [notices, setNotices] = useState<HeaderNotice[]>([]);
  const [noticeError, setNoticeError] = useState("");
  const [seenNotices, setSeenNotices] = useState<string[]>([]);
  const [dark, setDark] = useState(false);
  const [sessions, setSessions] = useState<{ id: number; name: string; default?: number }[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [languages, setLanguages] = useState<{ code: string; name: string }[]>([{ code: "en", name: "English" }]);
  const [language, setLanguage] = useState("en");
  const menuRef = useRef<HTMLDivElement>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const languageRef = useRef<HTMLDivElement>(null);
  const noticeRef = useRef<HTMLDivElement>(null);
  const schoolHeader = schoolName !== undefined;

  const displayName = schoolHeader
    ? user?.first_name || user?.email || "Admin"
    : [user?.first_name, user?.last_name].filter(Boolean).join(" ") || user?.email || "Admin";
  const workspace = sessions.find((item) => String(item.id) === workspaceId);
  const languageLabel = (languages.find((item) => item.code === language)?.code || language || "en").toUpperCase();
  const unseenNotices = notices.some((item) => !seenNotices.includes(item.id));
  const noticeHref = user?.role === "school_admin" ? "/school/announcement" : "/announcements";
  const initials = displayName
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() || "")
    .join("") || "A";

  useEffect(() => {
    const storedTheme = window.localStorage.getItem(THEME_KEY);
    const nextDark = storedTheme === "dark";
    setDark(nextDark);
    document.documentElement.dataset.theme = nextDark ? "dark" : "light";
    const storedLanguage = window.localStorage.getItem(LANGUAGE_KEY) || "en";
    setLanguage(storedLanguage);
    document.documentElement.lang = storedLanguage;
    setWorkspaceId(readWorkspace());
    setSeenNotices(readSeenNotices());
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadLanguages() {
      const response = await fetch("/api/languages").then((result) => result.json().catch(() => ({ data: [] }))).catch(() => ({ data: [] }));
      if (cancelled) return;
      const rows = Array.isArray(response?.data) ? response.data : [];
      if (rows.length) {
        setLanguages(rows.map((row: { code?: string; name?: string }) => ({ code: row.code || "en", name: row.name || "English" })));
      }
    }
    void loadLanguages();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!schoolHeader) return;
    let cancelled = false;
    async function loadHeaderData() {
      const sessionResult = await api<{ items?: { id: number; name: string; default?: number }[] }>("/school-admin/sessions");
      if (cancelled) return;
      const items = sessionResult.ok ? sessionResult.data.items || [] : [];
      setSessions(items);
      const stored = readWorkspace();
      const chosen = items.find((item) => String(item.id) === stored) || items.find((item) => item.default === 1) || items[0];
      if (chosen && String(chosen.id) !== stored) writeWorkspace(String(chosen.id));
      if (chosen) setWorkspaceId(String(chosen.id));
    }
    void loadHeaderData();
    function onWorkspace(event: Event) {
      setWorkspaceId((event as CustomEvent<string>).detail || "");
    }
    window.addEventListener("school-workspace-change", onWorkspace);
    return () => {
      cancelled = true;
      window.removeEventListener("school-workspace-change", onWorkspace);
    };
  }, [schoolHeader]);

  useEffect(() => {
    const role = user?.role;
    if (role !== "super_admin" && role !== "school_admin") return;
    let cancelled = false;
    async function loadNotices() {
      if (role === "school_admin") {
        const result = await adminApi<{ data?: { id: number; title?: string; description?: string }[] }>("/announcements");
        if (cancelled) return;
        if (!result.ok || !Array.isArray(result.data.data)) {
          setNotices([]);
          setNoticeError("Notifications could not be loaded.");
          return;
        }
        setNoticeError("");
        setNotices(result.data.data.slice(0, 8).map((row) => ({
          id: `announcement-${row.id}`,
          title: row.title || "Announcement",
          detail: row.description || "",
        })));
        return;
      }
      const result = await api<{ items?: { id: number; title?: string; body?: string | null }[] }>(
        "/super-admin/notifications?status=1&page=1&page_size=8",
      );
      if (cancelled) return;
      if (!result.ok) {
        setNotices([]);
        setNoticeError(result.status === 401 || result.status === 403 ? "Sign in again to view notifications." : "Notifications could not be loaded.");
        return;
      }
      setNoticeError("");
      setNotices((result.data.items || []).map((row) => ({
        id: `notification-${row.id}`,
        title: row.title || "Notification",
        detail: row.body || "",
      })));
    }
    void loadNotices();
    return () => {
      cancelled = true;
    };
  }, [user?.role]);

  useEffect(() => {
    function onDocClick(event: MouseEvent) {
      const target = event.target as Node;
      if (!menuRef.current?.contains(target)) setOpen(false);
      if (!workspaceRef.current?.contains(target)) setWorkspaceOpen(false);
      if (!languageRef.current?.contains(target)) setLanguageOpen(false);
      if (!noticeRef.current?.contains(target)) setNoticeOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function chooseWorkspace(id: string) {
    setWorkspaceId(id);
    writeWorkspace(id);
    setWorkspaceOpen(false);
  }

  function openNotices() {
    const nextOpen = !noticeOpen;
    setNoticeOpen(nextOpen);
    if (!nextOpen) return;
    const next = Array.from(new Set([...seenNotices, ...notices.map((item) => item.id)]));
    setSeenNotices(next);
    window.localStorage.setItem(SEEN_NOTICES_KEY, JSON.stringify(next));
  }

  function chooseLanguage(code: string) {
    setLanguage(code);
    window.localStorage.setItem(LANGUAGE_KEY, code);
    document.documentElement.lang = code;
    setLanguageOpen(false);
  }

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.dataset.theme = next ? "dark" : "light";
    window.localStorage.setItem(THEME_KEY, next ? "dark" : "light");
  }

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
      <div className="header-left">
        {schoolHeader ? (
          <div className="school-header-brand">
            <span className="sidebar-logo" aria-hidden>
              <IconLogoMark width={18} height={18} />
            </span>
            <span className="school-header-product">SchoolSarthi</span>
          </div>
        ) : null}
        <button
          type="button"
          className="icon-btn"
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
        >
          <IconMenu width={20} height={20} />
        </button>
        {schoolHeader ? (
          <span className="school-header-name">{schoolName || "Your school"}</span>
        ) : null}
      </div>

      <div className="header-right">
        {schoolHeader ? (
          <div className="workspace-switch" ref={workspaceRef}>
            <button
              type="button"
              className="workspace-pill"
              aria-expanded={workspaceOpen}
              aria-label="Active workspace"
              onClick={() => setWorkspaceOpen((value) => !value)}
            >
              <span className="workspace-icon" aria-hidden>
                <IconCalendar width={16} height={16} />
              </span>
              <span>
                <small className="workspace-kicker">Active workspace</small>
                <strong className="workspace-value">{workspace?.name || "No session"}</strong>
              </span>
              <IconChevron width={14} height={14} />
            </button>
            {workspaceOpen ? (
              <div className="dropdown-panel" role="menu">
                {sessions.length === 0 ? (
                  <p className="dropdown-item">No session years for this school.</p>
                ) : sessions.map((item) => (
                  <button key={item.id} type="button" className="dropdown-item" onClick={() => chooseWorkspace(String(item.id))}>
                    {item.name}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        {schoolHeader ? (
          <button type="button" className="icon-btn" aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} onClick={toggleTheme}>
            {dark ? <IconSun /> : <IconMoon />}
          </button>
        ) : null}
        <div className="language-switch" ref={languageRef}>
          <button type="button" className="lang-pill" aria-label="Language" aria-expanded={languageOpen} onClick={() => setLanguageOpen((value) => !value)}>
            <IconGlobe width={16} height={16} />
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

        <div className="language-switch" ref={noticeRef}>
          <button type="button" className="icon-btn" aria-label="Notifications" aria-expanded={noticeOpen} onClick={openNotices}>
            <IconBell width={18} height={18} />
            {unseenNotices ? <span className="badge-dot" /> : null}
          </button>
          {noticeOpen ? (
            <div className="dropdown-panel notice-panel" role="menu">
              {noticeError ? <p className="dropdown-item">{noticeError}</p> : null}
              {!noticeError && notices.length === 0 ? <p className="dropdown-item">No notifications.</p> : null}
              {notices.map((item) => (
                <Link key={item.id} href={noticeHref} className="dropdown-item" onClick={() => setNoticeOpen(false)}>
                  <strong>{item.title}</strong>
                  {item.detail ? <small>{item.detail}</small> : null}
                </Link>
              ))}
              <Link href={noticeHref} className="dropdown-item" onClick={() => setNoticeOpen(false)}>
                View all
              </Link>
            </div>
          ) : null}
        </div>

        <div className="user-menu-wrap" ref={menuRef}>
          <button
            type="button"
            className="user-trigger"
            onClick={() => setOpen((v) => !v)}
            aria-haspopup="menu"
            aria-expanded={open}
          >
            <span className="user-avatar" aria-hidden>{schoolHeader ? <IconUser /> : initials}</span>
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
              <Link href="/settings/password" className="dropdown-item" onClick={() => setOpen(false)}>
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

function IconMoon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <path d="M20 14.5A8 8 0 1 1 9.5 4 6.5 6.5 0 0 0 20 14.5Z" />
    </svg>
  );
}

function IconSun() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" />
    </svg>
  );
}

function IconUser() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <circle cx="12" cy="8" r="3" />
      <path d="M5 19c1.5-3 3.8-4.5 7-4.5S17.5 16 19 19" />
    </svg>
  );
}
