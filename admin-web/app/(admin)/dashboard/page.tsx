"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiErrorMessage, clearSession, getMe } from "@/lib/api";
import { loadDashboardPayload, type DashboardPayload } from "@/lib/dashboardData";
import { IconHome } from "@/lib/icons";
import { StatCard, StatCardSkeleton } from "@/components/dashboard/StatCard";
import { PageHeading } from "@/components/ui/PageHeading";
import { PaymentSummaryCards } from "@/components/payments/PaymentSummary";
import { RevenueChart, SubscriptionChart } from "@/components/dashboard/Charts";
import { QuickActions, RecentActivity, RecentSchools, RecentTransactions } from "@/components/dashboard/Lists";

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
  const [year, setYear] = useState(String(new Date().getFullYear()));

  useEffect(() => {
    let cancelled = false;

    async function load() {
      // Start the dashboard data alongside the profile check instead of after it.
      const payloadRequest = loadDashboardPayload(Number(year));
      const result = await getMe<UserMe>();
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
      const payload = await payloadRequest;
      if (cancelled) return;
      setDashboard(payload);
      setLoading(false);
    }

    void load();
    return () => {
      cancelled = true;
    };
    // The year only changes the registrations chart, which reloads below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  // A different year reloads the dashboard for that year's registrations.
  const firstYear = useRef(year);
  useEffect(() => {
    if (year === firstYear.current) return;
    firstYear.current = year;
    let cancelled = false;
    void loadDashboardPayload(Number(year)).then((payload) => {
      if (!cancelled) setDashboard(payload);
    });
    return () => {
      cancelled = true;
    };
  }, [year]);

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

      <section style={{ marginTop: 20 }}>
        <h2 style={{ margin: "0 0 12px", fontSize: 18 }}>Payment summary</h2>
        <PaymentSummaryCards />
      </section>

      <section className="panel-grid">
        <div className="panel-card">
          <div className="panel-card-header">
            <h2>School registrations</h2>
            <select
              className="panel-select"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              aria-label="Select year"
            >
              {[0, 1, 2].map((back) => {
                const value = String(new Date().getFullYear() - back);
                return (
                  <option key={value} value={value}>
                    {value}
                  </option>
                );
              })}
            </select>
          </div>
          {loading ? (
            <div className="skeleton" style={{ height: 240 }} />
          ) : dashboard?.revenue.some((point) => point.value > 0) ? (
            <RevenueChart points={dashboard.revenue} label={`Schools registered per month in ${year}`} />
          ) : (
            <div className="empty-state">No schools registered in {year}</div>
          )}
        </div>

        <div className="panel-card">
          <div className="panel-card-header">
            <h2>Schools by plan</h2>
          </div>
          {loading ? (
            <div className="skeleton" style={{ height: 240 }} />
          ) : dashboard?.packages.length ? (
            <SubscriptionChart slices={dashboard.packages} />
          ) : (
            <div className="empty-state">No school has an active plan yet</div>
          )}
        </div>
      </section>

      <section className="lower-grid">
        <div className="panel-card">
          <div className="panel-card-header">
            <h2>Recent payments</h2>
          </div>
          {loading ? (
            <div className="skeleton" style={{ height: 180 }} />
          ) : (
            <RecentTransactions rows={dashboard?.transactions || []} />
          )}
        </div>

        <div className="panel-card">
          <div className="panel-card-header">
            <h2>Recent activity</h2>
          </div>
          {loading ? (
            <div className="skeleton" style={{ height: 180 }} />
          ) : (
            <RecentActivity items={dashboard?.activity || []} />
          )}
        </div>

        <div className="panel-card">
          <div className="panel-card-header">
            <h2>Newest schools</h2>
          </div>
          {loading ? (
            <div className="skeleton" style={{ height: 180 }} />
          ) : (
            <RecentSchools rows={dashboard?.schools || []} />
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
