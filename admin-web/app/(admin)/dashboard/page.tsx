"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, apiErrorMessage, clearSession } from "@/lib/api";
import { loadDashboardPayload, type DashboardPayload } from "@/lib/dashboardData";
import { IconHome } from "@/lib/icons";
import { PageHeading, StatCard, StatCardSkeleton } from "@/components/dashboard/StatCard";
import { RevenueChart, SubscriptionChart } from "@/components/dashboard/Charts";
import { QuickActions, RecentActivity, RecentTransactions } from "@/components/dashboard/Lists";

type UserMe = {
  id?: string | number;
  email?: string;
  first_name?: string;
  last_name?: string;
  mobile?: string | null;
  role?: string;
  detail?: string;
};

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserMe | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [year, setYear] = useState("2026");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const result = await api<UserMe>("/auth/me");
      if (cancelled) return;

      if (result.status === 401) {
        clearSession();
        router.replace("/login");
        return;
      }

      if (!result.ok) {
        setError(apiErrorMessage(result.data, "Failed to load profile."));
        setLoading(false);
        return;
      }

      if (result.data.role === "school_admin") {
        router.replace("/school");
        return;
      }

      setUser(result.data);
      const payload = await loadDashboardPayload();
      if (cancelled) return;
      setDashboard(payload);
      setLoading(false);
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <div>
      <PageHeading
        title="Dashboard"
        description="Overview of your platform performance"
        icon={<IconHome width={22} height={22} />}
      />

      {error ? <div className="alert alert-danger">{error}</div> : null}
      {dashboard?.message ? <div className="alert alert-danger">{dashboard.message}</div> : null}

      <section className="stat-grid" aria-label="Key metrics">
        {loading
          ? Array.from({ length: 6 }).map((_, i) => <StatCardSkeleton key={i} />)
          : dashboard?.stats.map((stat) => <StatCard key={stat.id} data={stat} />)}
      </section>

      <section className="panel-grid">
        <div className="panel-card">
          <div className="panel-card-header">
            <h2>Revenue Overview</h2>
            <select
              className="panel-select"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              aria-label="Select year"
            >
              <option value="2026">2026</option>
              <option value="2025">2025</option>
            </select>
          </div>
          {loading ? (
            <div className="skeleton" style={{ height: 240 }} />
          ) : dashboard?.revenue.length ? (
            <RevenueChart points={dashboard.revenue} />
          ) : (
            <div className="empty-state">No revenue data available</div>
          )}
        </div>

        <div className="panel-card">
          <div className="panel-card-header">
            <h2>Subscription Distribution</h2>
          </div>
          {loading ? (
            <div className="skeleton" style={{ height: 240 }} />
          ) : dashboard?.packages.length ? (
            <SubscriptionChart slices={dashboard.packages} />
          ) : (
            <div className="empty-state">No subscription data available</div>
          )}
        </div>
      </section>

      <section className="lower-grid">
        <div className="panel-card">
          <div className="panel-card-header">
            <h2>Fee plans</h2>
          </div>
          {loading ? (
            <div className="skeleton" style={{ height: 180 }} />
          ) : (
            <RecentTransactions rows={dashboard?.transactions || []} />
          )}
        </div>

        <div className="panel-card">
          <div className="panel-card-header">
            <h2>Announcements</h2>
          </div>
          {loading ? (
            <div className="skeleton" style={{ height: 180 }} />
          ) : (
            <RecentActivity items={dashboard?.activity || []} />
          )}
        </div>
      </section>

      <section className="panel-card" style={{ marginBottom: 24 }}>
        <div className="panel-card-header">
          <h2>Quick Actions</h2>
        </div>
        <QuickActions />
      </section>

      {!loading && user ? (
        <p className="muted" style={{ fontSize: 12 }}>
          Signed in as {user.first_name} {user.last_name} ({user.email})
        </p>
      ) : null}
    </div>
  );
}
