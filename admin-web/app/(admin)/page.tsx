"use client";

import { useEffect, useState } from "react";
import { api, apiErrorMessage, clearSession } from "@/lib/api";
import { useRouter } from "next/navigation";

type UserMe = {
  id?: number;
  email?: string;
  first_name?: string;
  last_name?: string;
  mobile?: string | null;
  detail?: string;
};

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserMe | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

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
      } else {
        setUser(result.data);
      }
      setLoading(false);
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <div>
      <h1 className="h3 mb-3">Dashboard</h1>
      <p className="text-muted small mb-4">
        Signed-in user from <code>/api/v1/auth/me</code>
      </p>

      {loading ? <div className="text-muted">Loading…</div> : null}
      {error ? <div className="alert alert-danger">{error}</div> : null}

      {!loading && !error && user ? (
        <div className="border rounded p-4" style={{ maxWidth: 520 }}>
          <div className="mb-2">
            <span className="text-muted small d-block">Name</span>
            <strong>
              {user.first_name} {user.last_name}
            </strong>
          </div>
          <div className="mb-2">
            <span className="text-muted small d-block">Email</span>
            <strong>{user.email}</strong>
          </div>
          <div>
            <span className="text-muted small d-block">Mobile</span>
            <strong>{user.mobile || "—"}</strong>
          </div>
        </div>
      ) : null}
    </div>
  );
}
