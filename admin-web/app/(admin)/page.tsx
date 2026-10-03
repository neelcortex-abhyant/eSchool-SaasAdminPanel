"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type DashboardData = {
  students?: number;
  classes?: number;
  subjects?: number;
  attendances?: number;
  exams?: number;
  fees?: number;
  announcements?: number;
  leaves?: number;
  expenses?: number;
  schools?: number;
  packages?: number;
};

type DashboardResponse = {
  error?: boolean;
  message?: string;
  data?: DashboardData;
};

const CARDS: { key: keyof DashboardData; label: string; href: string }[] = [
  { key: "students", label: "Students", href: "/students" },
  { key: "classes", label: "Classes", href: "/classes" },
  { key: "subjects", label: "Subjects", href: "/subjects" },
  { key: "attendances", label: "Attendances", href: "/attendances" },
  { key: "exams", label: "Exams", href: "/exams" },
  { key: "fees", label: "Fees", href: "/fees" },
  { key: "announcements", label: "Announcements", href: "/announcements" },
  { key: "leaves", label: "Leaves", href: "/leaves" },
  { key: "expenses", label: "Expenses", href: "/expenses" },
  { key: "schools", label: "Schools", href: "/schools" },
  { key: "packages", label: "Packages", href: "/packages" },
];

export default function DashboardPage() {
  const [counts, setCounts] = useState<DashboardData>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const result = await api<DashboardResponse>("/dashboard");
      if (cancelled) return;

      if (!result.ok || result.data.error) {
        setError(result.data.message || "Failed to load dashboard.");
      } else {
        setCounts(result.data.data || {});
      }
      setLoading(false);
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <h1 className="h3 mb-3">Dashboard</h1>
      <p className="text-muted small mb-4">
        Counts from <code>/api/admin/dashboard</code>
      </p>

      {loading ? <div className="text-muted">Loading…</div> : null}
      {error ? <div className="alert alert-danger">{error}</div> : null}

      {!loading && !error ? (
        <div className="row g-3">
          {CARDS.map((card) => (
            <div key={card.key} className="col-6 col-md-4 col-xl-3">
              <Link href={card.href} className="text-decoration-none">
                <div className="border rounded p-3 h-100">
                  <div className="text-muted small">{card.label}</div>
                  <div className="fs-4 fw-semibold text-dark">
                    {counts[card.key] ?? 0}
                  </div>
                </div>
              </Link>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
