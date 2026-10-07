import type { MonthPoint, PackageSlice } from "@/lib/dashboardData";

export function RevenueChart({ points }: { points: MonthPoint[] }) {
  const width = 640;
  const height = 260;
  const padX = 36;
  const padY = 24;
  const max = Math.max(...points.map((p) => p.value), 1);
  const stepX = (width - padX * 2) / Math.max(points.length - 1, 1);

  const coords = points.map((p, i) => {
    const x = padX + i * stepX;
    const y = height - padY - (p.value / max) * (height - padY * 2);
    return { x, y, ...p };
  });

  const line = coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x} ${c.y}`).join(" ");
  const area = `${line} L ${coords[coords.length - 1]?.x ?? padX} ${height - padY} L ${padX} ${height - padY} Z`;

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Revenue overview chart">
        {[0, 0.25, 0.5, 0.75, 1].map((t) => {
          const y = height - padY - t * (height - padY * 2);
          return (
            <line
              key={t}
              x1={padX}
              x2={width - padX}
              y1={y}
              y2={y}
              stroke="#e8edf5"
              strokeWidth="1"
            />
          );
        })}
        <path d={area} fill="rgba(61, 187, 138, 0.14)" />
        <path d={line} fill="none" stroke="#3dbb8a" strokeWidth="2.5" strokeLinejoin="round" />
        {coords.map((c) => (
          <g key={c.month}>
            <circle cx={c.x} cy={c.y} r="3.5" fill="#2f5bff" />
            <title>
              {c.month}: {c.value}
            </title>
            <text x={c.x} y={height - 6} textAnchor="middle" fontSize="11" fill="#94a3b8">
              {c.month}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

export function SubscriptionChart({ slices }: { slices: PackageSlice[] }) {
  const size = 220;
  const stroke = 28;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const total = slices.reduce((sum, s) => sum + s.value, 0) || 1;
  let offset = 0;

  return (
    <div className="donut-layout">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Subscription distribution">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#eef2f7"
          strokeWidth={stroke}
        />
        {slices.map((slice) => {
          const length = (slice.value / total) * circumference;
          const el = (
            <circle
              key={slice.label}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={slice.color}
              strokeWidth={stroke}
              strokeDasharray={`${length} ${circumference - length}`}
              strokeDashoffset={-offset}
              strokeLinecap="butt"
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
            >
              <title>
                {slice.label}: {slice.value}%
              </title>
            </circle>
          );
          offset += length;
          return el;
        })}
        <text x="50%" y="48%" textAnchor="middle" fontSize="22" fontWeight="700" fill="#1e293b">
          {Math.round(total)}%
        </text>
        <text x="50%" y="58%" textAnchor="middle" fontSize="12" fill="#94a3b8">
          coverage
        </text>
      </svg>
      <div className="legend">
        {slices.map((slice) => (
          <span key={slice.label} className="legend-item">
            <span className="legend-dot" style={{ background: slice.color }} />
            {slice.label} · {slice.value}%
          </span>
        ))}
      </div>
    </div>
  );
}
