import React, { useMemo, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

// NDVI left (0..1), other metrics right. Years — chips, series — toggles.
// Forecast marked type=1 (dashed), actual — type=0 (solid).
export default function MetricsChart({ history = [] }) {
  const COLORS = {
    ndvi: "#10b981",
    temperature_deg_c: "#f59e0b",
    wind_speed_mps: "#3b82f6",
    cloudcover_pct: "#6b7280",
    clarity_pct: "#eab308",
    humidity_pct: "#06b6d4",
  };

  const base = useMemo(() => (history || []).filter((d) => d?.date), [history]);

  // ---- Years ----
  const years = useMemo(() => {
    const s = new Set();
    for (const d of base) {
      const y = getYear(d.date);
      if (Number.isFinite(y)) s.add(y);
    }
    return Array.from(s).sort((a, b) => b - a);
  }, [base]);

  const [year, setYear] = useState(years.length ? years[0] : "All");
  const dataByYear = useMemo(
    () =>
      year === "All" ? base : base.filter((d) => getYear(d.date) === year),
    [base, year]
  );

  // ---- Split into hist (solid) / fc (dashed) by `type` ----
  const KEYS = [
    "ndvi",
    "temperature_deg_c",
    "wind_speed_mps",
    "cloudcover_pct",
    "clarity_pct",
    "humidity_pct",
  ];
  const pointType = (row) => {
    console.log('row', row);
    if (row?.type === 0 || row?.type === 1) return row.type; // new
    if (row?.isForecast ?? row?.isForcast) return 1; // legacy support
    return 0;
  };

  const dataSplit = useMemo(() => {
    return (dataByYear || []).map((row) => {
      const t = pointType(row);
      const out = { date: row.date };
      for (const k of KEYS) {
        const v = row[k];
        out[`${k}__hist`] = t === 0 ? v ?? null : null;
        out[`${k}__fc`] = t === 1 ? v ?? null : null;
      }
      return out;
    });
  }, [dataByYear]);

  // ---- Toggles ----
  const [show, setShow] = useState({
    ndvi: true,
    temperature_deg_c: true,
    wind_speed_mps: true,
    cloudcover_pct: true,
    clarity_pct: true,
    humidity_pct: true,
  });

  const yLeftLabel = show.ndvi ? "NDVI" : "";
  const rightKeys = Object.entries(show)
    .filter(([k, on]) => on && k !== "ndvi")
    .map(([k]) => k);

  const rightDomain = useMemo(() => {
    if (rightKeys.length === 0) return [0, "auto"];
    let lo = Infinity,
      hi = -Infinity;
    for (const row of dataByYear) {
      for (const k of rightKeys) {
        const v = row[k];
        if (typeof v === "number" && !Number.isNaN(v)) {
          lo = Math.min(lo, v);
          hi = Math.max(hi, v);
        }
      }
    }
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [0, "auto"];
    const pad = (hi - lo) * 0.05 || 1;
    return [round(lo - pad), round(hi + pad)];
  }, [dataByYear, rightKeys]);

  return (
    <div className="w-full">
      {/* Year chips */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        {years.map((y) => (
          <Chip key={y} active={year === y} onClick={() => setYear(y)}>
            {y}
          </Chip>
        ))}
        {years.length > 1 && (
          <Chip active={year === "All"} onClick={() => setYear("All")}>
            All
          </Chip>
        )}
      </div>

      {/* Metric toggles */}
      <div className="flex gap-2 text-xs mb-2 flex-wrap">
        <Toggle
          label="NDVI"
          on={show.ndvi}
          onClick={() => setShow((s) => ({ ...s, ndvi: !s.ndvi }))}
        />
        <Toggle
          label="Temp (°C)"
          on={show.temperature_deg_c}
          onClick={() =>
            setShow((s) => ({ ...s, temperature_deg_c: !s.temperature_deg_c }))
          }
        />
        <Toggle
          label="Wind (m/s)"
          on={show.wind_speed_mps}
          onClick={() =>
            setShow((s) => ({ ...s, wind_speed_mps: !s.wind_speed_mps }))
          }
        />
        <Toggle
          label="Cloud (%)"
          on={show.cloudcover_pct}
          onClick={() =>
            setShow((s) => ({ ...s, cloudcover_pct: !s.cloudcover_pct }))
          }
        />
        <Toggle
          label="Sun (%)"
          on={show.clarity_pct}
          onClick={() =>
            setShow((s) => ({ ...s, clarity_pct: !s.clarity_pct }))
          }
        />
        <Toggle
          label="Humidity (%)"
          on={show.humidity_pct}
          onClick={() =>
            setShow((s) => ({ ...s, humidity_pct: !s.humidity_pct }))
          }
        />
      </div>

      {/* Chart */}
      <div className="h-[340px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={dataSplit}
            margin={{ top: 10, right: 20, left: 0, bottom: 10 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 12 }}
              tickFormatter={formatDate}
              minTickGap={24}
            />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 12 }}
              domain={[0, 1]}
              tickFormatter={fmtNDVI}
              label={{ value: yLeftLabel, angle: -90, position: "insideLeft" }}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 12 }}
              domain={rightDomain}
              tickFormatter={fmtNum2}
            />
            <Tooltip content={<HistoryTooltip />} />
            <Legend />

            {/* For each metric: solid hist + dashed forecast (hidden in legend) */}
            {show.ndvi && (
              <>
                <Line
                  type="monotone"
                  dataKey="ndvi__hist"
                  yAxisId="left"
                  name="NDVI"
                  dot={false}
                  strokeWidth={2}
                  stroke={COLORS.ndvi}
                  connectNulls={false}
                />
                <Line
                  type="monotone"
                  dataKey="ndvi__fc"
                  yAxisId="left"
                  name="NDVI (forecast)"
                  dot={false}
                  strokeWidth={2}
                  stroke={COLORS.ndvi}
                  strokeDasharray="6 4"
                  connectNulls={false}
                  legendType="none"
                />
              </>
            )}

            {show.temperature_deg_c && (
              <>
                <Line
                  type="monotone"
                  dataKey="temperature_deg_c__hist"
                  yAxisId="right"
                  name="Temp (°C)"
                  dot={false}
                  strokeWidth={1.5}
                  stroke={COLORS.temperature_deg_c}
                  connectNulls={false}
                />
                <Line
                  type="monotone"
                  dataKey="temperature_deg_c__fc"
                  yAxisId="right"
                  name="Temp (°C) (forecast)"
                  dot={false}
                  strokeWidth={1.5}
                  stroke={COLORS.temperature_deg_c}
                  strokeDasharray="6 4"
                  connectNulls={false}
                  hide
                />
              </>
            )}

            {show.wind_speed_mps && (
              <>
                <Line
                  type="monotone"
                  dataKey="wind_speed_mps__hist"
                  yAxisId="right"
                  name="Wind (m/s)"
                  dot={false}
                  strokeWidth={1.5}
                  stroke={COLORS.wind_speed_mps}
                  connectNulls={false}
                />
                <Line
                  type="monotone"
                  dataKey="wind_speed_mps__fc"
                  yAxisId="right"
                  name="Wind (m/s) (forecast)"
                  dot={false}
                  strokeWidth={1.5}
                  stroke={COLORS.wind_speed_mps}
                  strokeDasharray="6 4"
                  connectNulls={false}
                  hide
                />
              </>
            )}

            {show.cloudcover_pct && (
              <>
                <Line
                  type="monotone"
                  dataKey="cloudcover_pct__hist"
                  yAxisId="right"
                  name="Cloud (%)"
                  dot={false}
                  strokeWidth={1.5}
                  stroke={COLORS.cloudcover_pct}
                  connectNulls={false}
                />
                <Line
                  type="monotone"
                  dataKey="cloudcover_pct__fc"
                  yAxisId="right"
                  name="Cloud (%) (forecast)"
                  dot={false}
                  strokeWidth={1.5}
                  stroke={COLORS.cloudcover_pct}
                  strokeDasharray="6 4"
                  connectNulls={false}
                  hide
                />
              </>
            )}

            {show.clarity_pct && (
              <>
                <Line
                  type="monotone"
                  dataKey="clarity_pct__hist"
                  yAxisId="right"
                  name="Sun (%)"
                  dot={false}
                  strokeWidth={1.5}
                  stroke={COLORS.clarity_pct}
                  connectNulls={false}
                />
                <Line
                  type="monotone"
                  dataKey="clarity_pct__fc"
                  yAxisId="right"
                  name="Sun (%) (forecast)"
                  dot={false}
                  strokeWidth={1.5}
                  stroke={COLORS.clarity_pct}
                  strokeDasharray="6 4"
                  connectNulls={false}
                  hide
                />
              </>
            )}

            {show.humidity_pct && (
              <>
                <Line
                  type="monotone"
                  dataKey="humidity_pct__hist"
                  yAxisId="right"
                  name="Humidity (%)"
                  dot={false}
                  strokeWidth={1.5}
                  stroke={COLORS.humidity_pct}
                  connectNulls={false}
                />
                <Line
                  type="monotone"
                  dataKey="humidity_pct__fc"
                  yAxisId="right"
                  name="Humidity (%) (forecast)"
                  dot={false}
                  strokeWidth={1.5}
                  stroke={COLORS.humidity_pct}
                  strokeDasharray="6 4"
                  connectNulls={false}
                  hide
                />
              </>
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/* UI */
function Chip({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-full text-sm transition border ${
        active
          ? "bg-emerald-600 text-white border-emerald-600"
          : "bg-white text-gray-700 border-gray-200 hover:border-gray-300"
      }`}
    >
      {children}
      {active && <span className="ml-1">✓</span>}
    </button>
  );
}
function Toggle({ label, on, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-2 py-1 rounded-full border text-xs ${
        on
          ? "bg-emerald-50 border-emerald-200 text-emerald-700"
          : "bg-white border-gray-200 text-gray-700"
      }`}
    >
      {label}
    </button>
  );
}

/* helpers */
function getYear(v) {
  try {
    const d = typeof v === "string" ? new Date(v) : v;
    return d.getFullYear();
  } catch {
    return NaN;
  }
}
const nf2 = new Intl.NumberFormat(undefined, {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});
function fmtNDVI(v) {
  if (v == null || Number.isNaN(v)) return "";
  return Number(v)
    .toFixed(2)
    .replace(/\.?0+$/, "");
}
function fmtNum2(v) {
  if (v == null || Number.isNaN(v)) return "";
  return nf2.format(v);
}
function round(x, p = 2) {
  const m = Math.pow(10, p);
  return Math.round((x + Number.EPSILON) * m) / m;
}
function formatDate(v) {
  try {
    const d = typeof v === "string" ? new Date(v) : v;
    if (!(d instanceof Date) || Number.isNaN(d.getTime()))
      return String(v ?? "");
    return d.toISOString().slice(0, 10);
  } catch {
    return String(v ?? "");
  }
}

function HistoryTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) return null;
  const pick = (base) => {
    const h = payload.find((p) => p.dataKey === `${base}__hist`);
    const f = payload.find((p) => p.dataKey === `${base}__fc`);
    return h?.value ?? f?.value;
  };
  const rows = [
    ["NDVI", pick("ndvi"), (v) => round(v)],
    ["Temp", pick("temperature_deg_c"), (v) => `${round(v)} °C`],
    ["Wind", pick("wind_speed_mps"), (v) => `${round(v)} m/s`],
    ["Cloud", pick("cloudcover_pct"), (v) => `${round(v)} %`],
    ["Sun", pick("clarity_pct"), (v) => `${round(v)} %`],
    ["Humidity", pick("humidity_pct"), (v) => `${round(v)} %`],
  ];
  return (
    <div className="rounded-md border bg-white/95 p-2 text-xs shadow">
      <div className="font-medium mb-1">{formatDate(label)}</div>
      {rows.map(([k, v, fmt]) =>
        v == null ? null : <Row key={k} k={k} v={fmt(v)} />
      )}
    </div>
  );
}
function Row({ k, v }) {
  return (
    <div className="flex items-center justify-between gap-6">
      <span className="text-gray-600">{k}</span>
      <span className="font-mono">{v}</span>
    </div>
  );
}
