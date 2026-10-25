"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { sessionLabel, useSessions } from "@/components/people/academicOptions";
import { api, apiErrorMessage } from "@/lib/api";
import { readWorkspace, writeWorkspace } from "@/lib/workspace";
import { IconClasses, IconExam, IconFees, IconHome, IconUsers } from "@/lib/icons";
import type { SchoolRecord } from "@/lib/school";

type SchoolAdminMe = {
  id?: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  mobile?: string | null;
  role?: string;
  school_id?: number | null;
  status?: number;
};

export default function SchoolAdminPage() {
  const [school, setSchool] = useState<SchoolRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setNotFound(false);
    const [me, schoolResult] = await Promise.all([
      api<SchoolAdminMe>("/school-admin/me"),
      api<SchoolRecord>("/school-admin/school"),
    ]);
    if (me.status === 403 || schoolResult.status === 403) {
      setError("This account is not a school admin.");
      setLoading(false);
      return;
    }
    if (!me.ok) {
      setError(apiErrorMessage(me.data, "Unable to load your school admin profile."));
      setLoading(false);
      return;
    }
    if (schoolResult.status === 404) {
      setNotFound(true);
      setLoading(false);
      return;
    }
    if (!schoolResult.ok || !schoolResult.data?.id) {
      setError(apiErrorMessage(schoolResult.data, "Unable to load your school."));
      setLoading(false);
      return;
    }
    setSchool(schoolResult.data);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      {loading ? <ProfileSkeleton /> : null}

      {!loading && error ? (
        <section className="panel-card">
          <div className="alert alert-danger">{error}</div>
          <div className="page-actions">
            <button className="btn-pill btn-pill-green" type="button" onClick={() => void load()}>
              Retry
            </button>
          </div>
        </section>
      ) : null}

      {!loading && notFound ? (
        <section className="panel-card">
          <div className="empty-state">No school is assigned to this account.</div>
        </section>
      ) : null}

      {!loading && school ? <SchoolDashboard schoolId={school.id} /> : null}
    </div>
  );
}

type Summary = {
  students?: number;
  classes?: number;
  subjects?: number;
  exams?: number;
  fees?: number;
  attendance_today?: { present?: number; absent?: number };
  leaves_today?: { count?: number; items?: { id: number; reason: string | null }[] };
  finance_months?: { month: string; expenses: number; fee_charges: number }[];
};

/**
 * Counts, today's attendance and leaves, and fee/expense totals by month come from one
 * request to /school-admin/academics/summary, worked out on the server for this school only.
 */
function SchoolDashboard({ schoolId }: { schoolId: number }) {
  const [counts, setCounts] = useState<Record<string, number> | null>(null);
  const [attendance, setAttendance] = useState<{ present: number; absent: number } | null>(null);
  const [leaves, setLeaves] = useState<{ count: number; items: { id: number; reason: string }[] } | null>(null);
  const [months, setMonths] = useState<{ month: string; expenses: number; fee_charges: number }[]>([]);
  const sessions = useSessions();
  const [sessionId, setSessionId] = useState("");

  useEffect(() => {
    setSessionId(readWorkspace());
    function onWorkspace(event: Event) {
      setSessionId((event as CustomEvent<string>).detail || "");
    }
    window.addEventListener("school-workspace-change", onWorkspace);
    return () => window.removeEventListener("school-workspace-change", onWorkspace);
  }, []);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function loadCounts() {
      setLoading(true);
      setError("");
      const session = /^\d+$/.test(sessionId) ? `?session_year_id=${sessionId}` : "";
      const result = await api<Summary>(`/school-admin/academics/summary${session}`);
      if (cancelled) return;
      if (!result.ok) {
        setError(apiErrorMessage(result.data, "Unable to load dashboard counts."));
        setLoading(false);
        return;
      }
      const data = result.data;
      setCounts({
        students: Number(data.students ?? 0),
        classes: Number(data.classes ?? 0),
        subjects: Number(data.subjects ?? 0),
        exams: Number(data.exams ?? 0),
        fees: Number(data.fees ?? 0),
      });
      setAttendance({ present: Number(data.attendance_today?.present ?? 0), absent: Number(data.attendance_today?.absent ?? 0) });
      setLeaves({
        count: Number(data.leaves_today?.count ?? 0),
        items: (data.leaves_today?.items ?? []).map((row) => ({ id: row.id, reason: row.reason || "Leave" })),
      });
      setMonths((data.finance_months ?? []).map((row) => ({ month: row.month, expenses: Number(row.expenses || 0), fee_charges: Number(row.fee_charges || 0) })));
      setLoading(false);
    }
    void loadCounts();
    return () => {
      cancelled = true;
    };
  }, [schoolId, sessionId]);

  const peak = Math.max(1, ...months.flatMap((month) => [month.expenses, month.fee_charges]));

  return (
    <div className="school-dash">
      <header className="school-dash-title">
        <span className="school-dash-title-icon" aria-hidden>
          <IconHome width={18} height={18} />
        </span>
        <h1>Dashboard</h1>
      </header>
      {error ? <div className="alert alert-danger">{error}</div> : null}
      {loading && !counts ? <div className="panel-card"><div className="skeleton" style={{ height: 120 }} /></div> : null}
      <section className="school-stat-row">
        <Stat href="/school/students" label="Total students" value={counts?.students} icon={<IconUsers width={18} height={18} />} tone="green" />
        <Stat href="/school/academics/classes" label="Total classes" value={counts?.classes} icon={<IconClasses width={18} height={18} />} tone="teal" />
        <Stat href="/school/academics/subjects" label="Total subjects" value={counts?.subjects} icon={<IconClasses width={18} height={18} />} tone="blue" />
        <Stat href="/school/offline-exams" label="Total exams" value={counts?.exams} icon={<IconExam width={18} height={18} />} tone="navy" />
        <Stat href="/school/manage-fees" label="Fee definitions" value={counts?.fees} icon={<IconFees width={18} height={18} />} tone="slate" />
      </section>
      <section className="school-dash-grid">
        <article className="panel-card school-chart-card">
          <div className="school-card-head">
            <h2>Income &amp; Expense</h2>
            <select aria-label="Academic session" value={sessionId} onChange={(event) => { setSessionId(event.target.value); writeWorkspace(event.target.value); }}>
              <option value="">All sessions</option>
              {sessions.options.map((session) => (
                <option key={session.id} value={String(session.id)}>{sessionLabel(session)}</option>
              ))}
            </select>
          </div>
          <ul className="school-legend">
            <li><i className="is-green" /> Fee charges due</li>
            <li><i className="is-amber" /> Recorded expenses</li>
          </ul>
          {months.length === 0 ? (
            <p className="school-empty-note">No fee charges or expenses are recorded for this session.</p>
          ) : (
            <div className="school-bars" role="img" aria-label="Fee charges and expenses by month">
              {months.map((month) => (
                <div key={`${month.month}-${month.expenses}-${month.fee_charges}`} className="school-bar-col">
                  <div className="school-bar-pair">
                    <span style={{ height: `${(month.fee_charges / peak) * 100}%` }} className="is-fee" title={`Fee charges ${month.fee_charges}`} />
                    <span style={{ height: `${(month.expenses / peak) * 100}%` }} className="is-expense" title={`Expenses ${month.expenses}`} />
                  </div>
                  <small>{month.month}</small>
                </div>
              ))}
            </div>
          )}
          <p className="school-empty-note">Collected fee payments are not stored. Green bars are fee amounts due. Amber bars are expenses.</p>
          {attendance ? <p className="school-empty-note">Today: {attendance.present} present, {attendance.absent} absent or late.</p> : null}
        </article>
        <article className="panel-card school-leave-card">
          <div className="school-card-head">
            <h2>Leaves</h2>
            <Link className="workspace-pill" href="/school/student-leave">Today</Link>
          </div>
          {!leaves || leaves.count === 0 ? (
            <p className="school-leave-empty">All are present.</p>
          ) : (
            <ul className="school-leave-list">
              {leaves.items.map((item) => (
                <li key={item.id}>{item.reason}</li>
              ))}
            </ul>
          )}
        </article>
      </section>
    </div>
  );
}

function Stat({ href, label, value, icon, tone }: { href: string; label: string; value?: number; icon: ReactNode; tone: string }) {
  return (
    <Link className="school-stat" href={href}>
      <div>
        <p>{label}</p>
        <strong>{value === undefined ? "—" : value}</strong>
      </div>
      <span className={`school-stat-icon is-${tone}`} aria-hidden>
        {icon}
      </span>
    </Link>
  );
}

function ProfileSkeleton() {
  return (
    <div>
      <div className="school-profile-header">
        <div className="school-profile-identity">
          <div className="skeleton school-avatar" />
          <div>
            <div className="skeleton" style={{ height: 28, width: 220, marginBottom: 8 }} />
            <div className="skeleton" style={{ height: 16, width: 140 }} />
          </div>
        </div>
      </div>
      <section className="panel-grid">
        <div className="panel-card">
          <div className="skeleton" style={{ height: 160 }} />
        </div>
        <div className="panel-card">
          <div className="skeleton" style={{ height: 160 }} />
        </div>
      </section>
    </div>
  );
}
