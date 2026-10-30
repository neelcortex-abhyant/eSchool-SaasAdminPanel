"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { ExtrasPage } from "@/components/extras/Frame";
import { PlacementFilters, useCurrentSessionId } from "@/components/teaching/Pickers";
import { downloadText } from "@/lib/operations/export";
import { formatValue, loadReport, REPORT_CATEGORIES, reportCsv, type Chart, type Report, type ReportCategory, type ReportFilter, type ReportTable } from "@/lib/reports/analytics";
import { IconChart } from "@/lib/icons";

function iso(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

/** The last six months, ending today. */
export function defaultRange(now = new Date()): { from: string; to: string } {
  return { from: iso(new Date(now.getFullYear(), now.getMonth() - 5, 1)), to: iso(now) };
}

const PRESETS: { label: string; range: (now: Date) => { from: string; to: string } }[] = [
  { label: "This month", range: (now) => ({ from: iso(new Date(now.getFullYear(), now.getMonth(), 1)), to: iso(now) }) },
  { label: "Last 3 months", range: (now) => ({ from: iso(new Date(now.getFullYear(), now.getMonth() - 2, 1)), to: iso(now) }) },
  { label: "Last 6 months", range: (now) => defaultRange(now) },
  { label: "This year", range: (now) => ({ from: iso(new Date(now.getFullYear(), 0, 1)), to: iso(now) }) },
];

export function ReportsDashboard() {
  return (
    <ExtrasPage title="Reports & analytics" description="Students, academics, finance, staff and transport in one place, for the dates and classes you choose." icon={<IconChart width={18} height={18} />}>
      <ReportsBody />
    </ExtrasPage>
  );
}

function isCategory(value: string | null): value is ReportCategory {
  return REPORT_CATEGORIES.some((item) => item.key === value);
}

function ReportsBody() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const requested = params.get("category");
  const category: ReportCategory = isCategory(requested) ? requested : "students";
  const meta = REPORT_CATEGORIES.find((item) => item.key === category) ?? REPORT_CATEGORIES[0];

  const currentSessionId = useCurrentSessionId();
  const [placement, setPlacement] = useState<{ sessionId: number | ""; classId: number | ""; sectionId: number | "" } | null>(null);
  const chosen = placement ?? { sessionId: currentSessionId, classId: "", sectionId: "" };
  const [range, setRange] = useState(defaultRange);
  const rangeProblem = !range.from || !range.to ? "Choose both dates." : range.from > range.to ? "The start date is after the end date." : "";

  const usesPlacement = meta.filters.includes("placement");
  const filter: ReportFilter = { ...(usesPlacement ? chosen : { sessionId: "", classId: "", sectionId: "" }), from: range.from, to: range.to };
  const key = JSON.stringify([category, filter]);
  const report = useReport(
    // eslint-disable-next-line react-hooks/exhaustive-deps
    useCallback(() => loadReport(category, filter), [key]),
    !rangeProblem,
  );

  const choose = (next: ReportCategory) => {
    const query = new URLSearchParams(params.toString());
    query.set("category", next);
    router.replace(`${pathname}?${query.toString()}`, { scroll: false });
  };

  const exportCsv = () => {
    if (!report.data) return;
    downloadText(`${category}-report-${range.from}-to-${range.to}.csv`, reportCsv(report.data, `${meta.label} report, ${range.from} to ${range.to}`));
  };

  return (
    <>
      <nav className="acad-tabs rpt-tabs ops-no-print" aria-label="Report category" role="tablist">
        {REPORT_CATEGORIES.map((item) => (
          <button key={item.key} type="button" role="tab" aria-selected={item.key === category} className={`acad-tab${item.key === category ? " is-active" : ""}`} onClick={() => choose(item.key)}>
            {item.label}
          </button>
        ))}
      </nav>

      <div className="school-filters rpt-filters ops-no-print">
        <label className="ops-filter-label">
          From
          <input type="date" value={range.from} max={range.to || undefined} onChange={(event) => setRange({ ...range, from: event.target.value })} />
        </label>
        <label className="ops-filter-label">
          To
          <input type="date" value={range.to} min={range.from || undefined} onChange={(event) => setRange({ ...range, to: event.target.value })} />
        </label>
        <select aria-label="Date range" value="" onChange={(event) => {
          const preset = PRESETS[Number(event.target.value)];
          if (preset) setRange(preset.range(new Date()));
        }}>
          <option value="">Quick range…</option>
          {PRESETS.map((preset, index) => (
            <option key={preset.label} value={index}>
              {preset.label}
            </option>
          ))}
        </select>
        {usesPlacement ? <PlacementFilters sessionId={chosen.sessionId} classId={chosen.classId} sectionId={chosen.sectionId} onChange={setPlacement} /> : null}
        <span className="rpt-actions">
          <button type="button" className="btn-pill btn-pill-green-soft" onClick={exportCsv} disabled={!report.data || report.loading}>
            Export CSV
          </button>
          <button type="button" className="btn-pill btn-pill-green-soft" onClick={() => window.print()} disabled={!report.data || report.loading}>
            Print / PDF
          </button>
        </span>
      </div>

      <h2 className="rpt-print-title">
        {meta.label} report · {range.from} to {range.to}
      </h2>

      {rangeProblem ? <div className="alert alert-warning">{rangeProblem}</div> : null}
      <ErrorAlert error={report.error} onRetry={report.reload} />
      {report.data?.warnings.length ? (
        <div className="alert alert-warning" role="status">
          Some parts couldn&apos;t be loaded: {report.data.warnings.join(" · ")}
        </div>
      ) : null}

      {report.loading && !report.data ? <ReportSkeleton /> : report.data ? <ReportView report={report.data} busy={report.loading} /> : null}
    </>
  );
}

/** Loads one report; the last answer stays on screen while the next one loads, and a late answer for old filters is dropped. */
function useReport(loader: () => Promise<Report>, enabled: boolean) {
  const [data, setData] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const requestId = useRef(0);
  const reload = useCallback(async () => {
    const id = ++requestId.current;
    if (!enabled) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await loader();
      if (id === requestId.current) setData(result);
    } catch (caught) {
      if (id === requestId.current) {
        setData(null);
        setError(caught);
      }
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [loader, enabled]);
  useEffect(() => {
    void reload();
  }, [reload]);
  return { data, loading, error, reload };
}

function ReportSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading report">
      <div className="teach-stats">
        {[0, 1, 2, 3, 4].map((index) => (
          <div key={index} className="teach-stat">
            <div className="skeleton" style={{ height: 22, width: "60%" }} />
            <div className="skeleton" style={{ height: 12, width: "80%", marginTop: 8 }} />
          </div>
        ))}
      </div>
      <div className="rpt-charts">
        {[0, 1].map((index) => (
          <div key={index} className="resource-card rpt-chart">
            <div className="skeleton" style={{ height: 180 }} />
          </div>
        ))}
      </div>
    </div>
  );
}

function ReportView({ report, busy }: { report: Report; busy: boolean }) {
  return (
    <div className="rpt-body" aria-busy={busy}>
      <div className="teach-stats rpt-cards">
        {report.cards.map((card) => (
          <div key={card.label} className={`teach-stat${card.tone ? ` is-${card.tone}` : ""}`}>
            <span className="teach-stat-value">{card.value}</span>
            <span className="teach-stat-label">{card.label}</span>
            {card.note ? <span className="rpt-card-note">{card.note}</span> : null}
          </div>
        ))}
      </div>
      <div className="rpt-charts">
        {report.charts.map((chart) => (
          <section key={chart.title} className="resource-card rpt-chart" aria-label={chart.title}>
            <h3>{chart.title}</h3>
            {chart.points.length === 0 || chart.points.every((point) => point.value === 0) ? <div className="empty-state">Nothing to chart for these filters.</div> : chart.kind === "line" ? <LineChart chart={chart} /> : <BarChart chart={chart} />}
          </section>
        ))}
      </div>
      {report.tables.map((table) => (
        <TableCard key={table.title} table={table} />
      ))}
      {report.notes.map((note) => (
        <p key={note} className="muted rpt-note">
          {note}
        </p>
      ))}
    </div>
  );
}

const BAR_LIMIT = 12;

/** Horizontal bars: long labels stay readable and it fits a phone. */
export function BarChart({ chart }: { chart: Chart }) {
  const points = chart.points.slice(0, BAR_LIMIT);
  const max = chart.format === "percent" ? 100 : Math.max(...points.map((point) => point.value), 1);
  return (
    <>
      <ul className="rpt-bars">
        {points.map((point) => (
          <li key={point.label} className="rpt-bar-row" title={`${point.label}: ${formatValue(point.value, chart.format)}`}>
            <span className="rpt-bar-label">{point.label}</span>
            <span className="rpt-bar-track" aria-hidden>
              <span className="rpt-bar-fill" style={{ width: `${Math.max((point.value / max) * 100, point.value ? 1.5 : 0)}%` }} />
            </span>
            <span className="rpt-bar-value">{formatValue(point.value, chart.format)}</span>
          </li>
        ))}
      </ul>
      {chart.points.length > BAR_LIMIT ? <p className="muted rpt-note">Showing {BAR_LIMIT} of {chart.points.length}; the table below has them all.</p> : null}
    </>
  );
}

/** Trend over months, with a hover readout for the nearest month. */
export function LineChart({ chart }: { chart: Chart }) {
  const [active, setActive] = useState<number | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const width = 640;
  const height = 220;
  const pad = { left: 12, right: 12, top: 20, bottom: 28 };
  const max = Math.max(...chart.points.map((point) => point.value), 1);
  const step = (width - pad.left - pad.right) / Math.max(chart.points.length - 1, 1);
  const coords = chart.points.map((point, index) => ({ ...point, x: pad.left + index * step, y: height - pad.bottom - (point.value / max) * (height - pad.top - pad.bottom) }));
  const line = coords.map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`).join(" ");
  const labelEvery = Math.ceil(coords.length / 8);
  useEffect(() => setActive(null), [chart]);

  const onMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const box = svg.current?.getBoundingClientRect();
    if (!box || !box.width) return;
    const x = ((event.clientX - box.left) / box.width) * width;
    setActive(Math.min(Math.max(Math.round((x - pad.left) / step), 0), coords.length - 1));
  };
  const shown = active !== null ? coords[active] : null;

  return (
    <div className="rpt-line">
      <div className="rpt-readout" aria-live="polite">
        {shown ? (
          <>
            <strong>{formatValue(shown.value, chart.format)}</strong> <span className="muted">{shown.label}</span>
          </>
        ) : (
          <span className="muted">Peak {formatValue(Math.max(...chart.points.map((point) => point.value)), chart.format)} · hover for a month</span>
        )}
      </div>
      <svg ref={svg} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${chart.title}: ${chart.points.map((point) => `${point.label} ${formatValue(point.value, chart.format)}`).join(", ")}`} onPointerMove={onMove} onPointerLeave={() => setActive(null)}>
        {[0, 0.5, 1].map((t) => {
          const y = height - pad.bottom - t * (height - pad.top - pad.bottom);
          return (
            <g key={t}>
              <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} className="rpt-grid" />
              {t ? (
                <text x={pad.left} y={y - 4} className="rpt-axis">
                  {formatValue(Math.round(max * t * 100) / 100, chart.format)}
                </text>
              ) : null}
            </g>
          );
        })}
        <path d={`${line} L ${coords[coords.length - 1]?.x ?? pad.left} ${height - pad.bottom} L ${pad.left} ${height - pad.bottom} Z`} className="rpt-area" />
        <path d={line} className="rpt-stroke" />
        {shown ? <line x1={shown.x} x2={shown.x} y1={pad.top} y2={height - pad.bottom} className="rpt-cross" /> : null}
        {coords.map((point, index) => (
          <g key={point.label}>
            <circle cx={point.x} cy={point.y} r={active === index ? 5 : 3.5} className="rpt-dot" />
            {index % labelEvery === 0 || index === coords.length - 1 ? (
              <text x={point.x} y={height - 8} textAnchor={index === 0 ? "start" : index === coords.length - 1 ? "end" : "middle"} className="rpt-axis">
                {point.label}
              </text>
            ) : null}
          </g>
        ))}
      </svg>
    </div>
  );
}

function TableCard({ table }: { table: ReportTable }) {
  return (
    <section className="resource-card rpt-table" aria-label={table.title}>
      <h3>{table.title}</h3>
      <div className="table-wrap">
        <table className="data-table acad-table">
          <thead>
            <tr>
              {table.columns.map((column) => (
                <th key={column} scope="col">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.length === 0 ? (
              <tr className="acad-empty-row">
                <td colSpan={table.columns.length}>
                  <div className="empty-state">{table.empty}</div>
                </td>
              </tr>
            ) : (
              table.rows.map((row, index) => (
                <tr key={index}>
                  {row.map((cell, column) => (
                    <td key={column} data-label={table.columns[column]}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
