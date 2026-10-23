"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, getMe } from "@/lib/api";
import { SCHOOL_ADMIN_NAV } from "@/lib/nav";
import Sidebar from "@/components/layout/Sidebar";
import TopHeader from "@/components/layout/TopHeader";

type HeaderUser = {
  first_name?: string;
  last_name?: string;
  email?: string;
  role?: string;
};

type SchoolHeader = {
  name?: string | null;
  code?: string | null;
};

export default function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [user, setUser] = useState<HeaderUser | null>(null);
  const [school, setSchool] = useState<SchoolHeader | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadUser() {
      const result = await getMe<HeaderUser>();
      if (cancelled) return;
      if (!result.ok) return;
      setUser(result.data);
      if (result.data.role === "school_admin") {
        const schoolResult = await api<SchoolHeader>("/school-admin/school");
        if (!cancelled && schoolResult.ok) setSchool(schoolResult.data);
      }
    }
    void loadUser();
    return () => {
      cancelled = true;
    };
  }, []);

  const schoolAdmin = user?.role === "school_admin";

  useEffect(() => {
    if (!schoolAdmin) return;
    const allowed = pathname === "/school" || pathname.startsWith("/school/") || pathname === "/settings" || pathname.startsWith("/settings/");
    if (!allowed) router.replace("/school");
  }, [schoolAdmin, pathname, router]);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    function onResize() {
      if (window.innerWidth > 900) setMobileOpen(false);
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  function toggleSidebar() {
    if (typeof window !== "undefined" && window.innerWidth <= 900) {
      setMobileOpen((v) => !v);
      return;
    }
    setCollapsed((v) => !v);
  }

  const shellClass = [
    "admin-shell",
    schoolAdmin ? "is-school" : "",
    collapsed ? "is-collapsed" : "",
    mobileOpen ? "is-mobile-open" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={shellClass}>
      {mobileOpen ? (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Close menu"
          onClick={() => setMobileOpen(false)}
        />
      ) : null}

      <Sidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onNavigate={() => setMobileOpen(false)}
        navItems={schoolAdmin ? SCHOOL_ADMIN_NAV : undefined}
        secondaryItems={schoolAdmin ? [] : undefined}
        subtitle={schoolAdmin ? "School Admin" : "Admin Panel"}
      />

      <div className="admin-main">
        <TopHeader
          user={user}
          onToggleSidebar={toggleSidebar}
          schoolName={schoolAdmin ? school?.name : undefined}
          schoolCode={schoolAdmin ? school?.code : undefined}
        />
        <div className="admin-content">{children}</div>
      </div>
    </div>
  );
}
