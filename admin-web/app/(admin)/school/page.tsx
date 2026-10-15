"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { adminApi, adminErrorMessage } from "@/lib/adminApi";
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

type AdminRow = {
  id: number;
  school_id?: number | null;
  session_year_id?: number | null;
  due_date?: string | null;
  due_charges?: number | null;
  date?: string | null;
  amount?: number | null;
  type?: number | null;
  reason?: string | null;
  from_date?: string | null;
  to_date?: string | null;
};

function owned(rows: AdminRow[] | undefined, schoolId: number) {
  return (rows || []).filter((row) => Number(row.school_id) === schoolId);
}

function SchoolDashboard({ schoolId }: { schoolId: number }) {
  const [counts, setCounts] = useState<Record<string, number> | null>(null);
  const [attendance, setAttendance] = useState<{ present: number; absent: number } | null>(null);
  const [leaves, setLeaves] = useState<{ count: number; items: { id: number; reason: string }[] } | null>(null);
  const [months, setMonths] = useState<{ month: string; expenses: number; fee_charges: number }[]>([]);
  const [sessions, setSessions] = useState<number[]>([]);
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
      const [students, classes, subjects, exams, fees, expenses, attendances, leaveRows] = await Promise.all([
        adminApi<{ data?: AdminRow[] }>("/students"),
        adminApi<{ data?: AdminRow[] }>("/classes"),
        adminApi<{ data?: AdminRow[] }>("/subjects"),
        adminApi<{ data?: AdminRow[] }>("/exams"),
        adminApi<{ data?: AdminRow[] }>("/fees"),
        adminApi<{ data?: AdminRow[] }>("/expenses"),
        adminApi<{ data?: AdminRow[] }>("/attendances"),
        adminApi<{ data?: AdminRow[] }>("/leaves"),
      ]);
      if (cancelled) return;
      const failed = [students, classes, subjects, exams, fees, expenses, attendances, leaveRows].find((result) => !result.ok);
      if (failed) {
        setError(adminErrorMessage(failed.data, "Unable to load dashboard counts."));
        setLoading(false);
        return;
      }
      const feeRows = owned(fees.data.data, schoolId).filter((row) => !sessionId || String(row.session_year_id) === sessionId);
      const expenseRows = owned(expenses.data.data, schoolId).filter((row) => !sessionId || String(row.session_year_id) === sessionId);
      const buckets = new Map<string, { month: string; expenses: number; fee_charges: number }>();
      feeRows.forEach((row) => {
        const month = (row.due_date || "").slice(0, 7);
        if (!month) return;
        const bucket = buckets.get(month) || { month, expenses: 0, fee_charges: 0 };
        bucket.fee_charges += Number(row.due_charges || 0);
        buckets.set(month, bucket);
      });
      expenseRows.forEach((row) => {
        const month = (row.date || "").slice(0, 7);
        if (!month) return;
        const bucket = buckets.get(month) || { month, expenses: 0, fee_charges: 0 };
        bucket.expenses += Number(row.amount || 0);
        buckets.set(month, bucket);
      });
      const today = new Date().toISOString().slice(0, 10);
      const todayAttendance = owned(attendances.data.data, schoolId).filter((row) => (row.date || "").slice(0, 10) === today);
      const todayLeaves = owned(leaveRows.data.data, schoolId).filter((row) => {
        const from = (row.from_date || "").slice(0, 10);
        const to = (row.to_date || "").slice(0, 10);
        return from && to && from <= today && today <= to;
      });
      const sessionIds = Array.from(new Set(
        [...owned(fees.data.data, schoolId), ...owned(expenses.data.data, schoolId)]
          .map((row) => row.session_year_id)
          .filter((id): id is number => typeof id === "number"),
      ));
      setSessions(sessionIds);
      setCounts({
        students: owned(students.data.data, schoolId).length,
        classes: owned(classes.data.data, schoolId).length,
        subjects: owned(subjects.data.data, schoolId).length,
        exams: owned(exams.data.data, schoolId).length,
        fees: owned(fees.data.data, schoolId).length,
      });
      setAttendance({
        present: todayAttendance.filter((row) => row.type === 1).length,
        absent: todayAttendance.filter((row) => row.type !== 1).length,
      });
      setLeaves({
        count: todayLeaves.length,
        items: todayLeaves.slice(0, 8).map((row) => ({ id: row.id, reason: row.reason || "Leave" })),
      });
      setMonths(Array.from(buckets.values()).sort((a, b) => a.month.localeCompare(b.month)));
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
        <Stat href="/school/classes" label="Total classes" value={counts?.classes} icon={<IconClasses width={18} height={18} />} tone="teal" />
        <Stat href="/school/subjects" label="Total subjects" value={counts?.subjects} icon={<IconClasses width={18} height={18} />} tone="blue" />
        <Stat href="/school/exams" label="Total exams" value={counts?.exams} icon={<IconExam width={18} height={18} />} tone="navy" />
        <Stat href="/school/fees" label="Fee definitions" value={counts?.fees} icon={<IconFees width={18} height={18} />} tone="slate" />
      </section>
      <section className="school-dash-grid">
        <article className="panel-card school-chart-card">
          <div className="school-card-head">
            <h2>Income &amp; Expense</h2>
            <select aria-label="Academic session" value={sessionId} onChange={(event) => { setSessionId(event.target.value); writeWorkspace(event.target.value); }}>
              <option value="">All sessions</option>
              {sessions.map((session) => (
                <option key={session} value={session}>Session {session}</option>
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
            <Link className="workspace-pill" href="/school/leaves">Today</Link>
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
