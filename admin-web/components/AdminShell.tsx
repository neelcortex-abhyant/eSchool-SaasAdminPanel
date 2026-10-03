"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { api } from "@/lib/api";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/students", label: "Students" },
  { href: "/classes", label: "Classes" },
  { href: "/subjects", label: "Subjects" },
  { href: "/attendances", label: "Attendances" },
  { href: "/exams", label: "Exams" },
  { href: "/fees", label: "Fees" },
  { href: "/announcements", label: "Announcements" },
  { href: "/leaves", label: "Leaves" },
  { href: "/expenses", label: "Expenses" },
  { href: "/schools", label: "Schools" },
  { href: "/packages", label: "Packages" },
  { href: "/settings", label: "Settings" },
] as const;

export default function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  async function logout() {
    await api("/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="container-fluid">
      <div className="row min-vh-100">
        <aside className="col-12 col-md-3 col-lg-2 border-end bg-light p-3">
          <div className="d-flex align-items-center justify-content-between mb-3">
            <Link href="/" className="text-decoration-none fw-semibold text-dark">
              eSchool Admin
            </Link>
          </div>
          <nav className="nav nav-pills flex-column gap-1">
            {NAV.map((item) => {
              const active =
                item.href === "/"
                  ? pathname === "/"
                  : pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`nav-link ${active ? "active" : "text-dark"}`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <button
            type="button"
            className="btn btn-outline-secondary btn-sm w-100 mt-4"
            onClick={logout}
          >
            Log out
          </button>
        </aside>
        <main className="col-12 col-md-9 col-lg-10 p-4">{children}</main>
      </div>
    </div>
  );
}
