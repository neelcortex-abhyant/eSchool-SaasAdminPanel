"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";

type Subscription = {
  id: number;
  package_id: number;
  status: number;
  cycle: string;
  start_date: string;
  end_date: string;
};

type Assignment = {
  id: number;
  addon_id: number;
  status: number;
  start_date: string | null;
  end_date: string | null;
};

export function SchoolBilling({ schoolId }: { schoolId: number }) {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [addons, setAddons] = useState<Assignment[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [packageId, setPackageId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [cycle, setCycle] = useState("monthly");
  const [addonId, setAddonId] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    const [subs, assigned] = await Promise.all([
      api<{ items?: Subscription[] }>(`/super-admin/schools/${schoolId}/subscriptions?page=1&page_size=50`),
      api<{ items?: Assignment[] }>(`/super-admin/schools/${schoolId}/addons?page=1&page_size=50`),
    ]);
    if (!subs.ok) setError(apiErrorMessage(subs.data, "Unable to load subscriptions."));
    else setSubscriptions(subs.data.items || []);
    if (assigned.ok) setAddons(assigned.data.items || []);
  }

  useEffect(() => {
    void load();
  }, [schoolId]);

  async function onSubscribe(event: FormEvent) {
    event.preventDefault();
    if (!packageId || !startDate || !endDate) {
      setError("Enter a plan ID, start date, and end date.");
      return;
    }
    setSaving(true);
    setError("");
    const result = await api(`/super-admin/schools/${schoolId}/subscriptions`, {
      method: "POST",
      body: JSON.stringify({
        package_id: Number(packageId),
        start_date: startDate,
        end_date: endDate,
        cycle,
        auto_renew: 1,
        status: 1,
      }),
    });
    setSaving(false);
    if (!result.ok) {
      setError(apiErrorMessage(result.data, "Unable to create the subscription."));
      return;
    }
    setNotice("Subscription created.");
    setPackageId("");
    await load();
  }

  async function onAssign(event: FormEvent) {
    event.preventDefault();
    if (!addonId) {
      setError("Enter an add-on ID.");
      return;
    }
    setSaving(true);
    setError("");
    const result = await api(`/super-admin/schools/${schoolId}/addons`, {
      method: "POST",
      body: JSON.stringify({ addon_id: Number(addonId) }),
    });
    setSaving(false);
    if (!result.ok) {
      setError(apiErrorMessage(result.data, "Unable to assign the add-on."));
      return;
    }
    setNotice("Add-on assigned.");
    setAddonId("");
    await load();
  }

  return (
    <section className="panel-grid">
      <article className="panel-card">
        <div className="panel-card-header">
          <h2>Subscriptions</h2>
        </div>
        {error ? <div className="alert alert-danger">{error}</div> : null}
        {notice ? <div className="alert alert-info">{notice}</div> : null}
        <form className="resource-fields" onSubmit={onSubscribe}>
          <div className="form-field">
            <label htmlFor="sub-plan">Plan ID *</label>
            <input id="sub-plan" type="number" value={packageId} onChange={(e) => setPackageId(e.target.value)} />
          </div>
          <div className="form-field">
            <label htmlFor="sub-cycle">Cycle</label>
            <select id="sub-cycle" value={cycle} onChange={(e) => setCycle(e.target.value)}>
              <option value="monthly">Monthly</option>
              <option value="yearly">Yearly</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="sub-start">Start *</label>
            <input id="sub-start" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </div>
          <div className="form-field">
            <label htmlFor="sub-end">End *</label>
            <input id="sub-end" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </div>
          <div className="resource-actions">
            <button className="btn-pill btn-pill-green" type="submit" disabled={saving}>
              {saving ? "Saving…" : "Add subscription"}
            </button>
          </div>
        </form>
        <RecordTable
          rows={subscriptions.map((row) => ({
            id: row.id,
            plan: row.package_id,
            cycle: row.cycle,
            status: row.status,
            start: row.start_date,
            end: row.end_date,
          }))}
        />
      </article>
      <article className="panel-card">
        <div className="panel-card-header">
          <h2>Add-ons</h2>
        </div>
        <form onSubmit={onAssign}>
          <div className="form-field">
            <label htmlFor="addon-id">Add-on ID *</label>
            <input id="addon-id" type="number" value={addonId} onChange={(e) => setAddonId(e.target.value)} />
          </div>
          <div className="resource-actions">
            <button className="btn-pill btn-pill-green" type="submit" disabled={saving}>
              Assign add-on
            </button>
          </div>
        </form>
        <RecordTable
          rows={addons.map((row) => ({
            id: row.id,
            addon: row.addon_id,
            status: row.status,
            start: row.start_date,
            end: row.end_date,
          }))}
        />
      </article>
    </section>
  );
}

function RecordTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) return <div className="empty-state">No records.</div>;
  const keys = Object.keys(rows[0]);
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {keys.map((key) => (
              <th key={key}>{key}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String(row.id)}>
              {keys.map((key) => (
                <td key={key}>{row[key] === null || row[key] === undefined || row[key] === "" ? "—" : String(row[key])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
