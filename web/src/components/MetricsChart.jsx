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

// Unified chart: shows NDVI on left axis, weather metrics on right axis with toggles
export default function MetricsChart({ history = [] }) {
  const COLORS = {
    ndvi: "#10b981", // emerald
    temperature_deg_c: "#f59e0b", // amber
    wind_speed_mps: "#3b82f6", // blue
    cloudcover_pct: "#6b7280", // gray
    clarity_pct: "#eab308", // yellow
    humidity_pct: "#06b6d4", // cyan
  };

  // Normalize and keep only rows with date
  const chartData = useMemo(
    () => (history || []).filter((d) => d?.date),
    [history]
  );

  // --- Year chips ---
  // Collect unique years present in the data, sort desc (2025, 2024, ...)
  const years = useMemo(() => {
    const set = new Set();
    for (const d of chartData) {
      const y = getYear(d.date);
      if (Number.isFinite(y)) set.add(y);
    }
    return Array.from(set).sort((a, b) => b - a);
  }, [chartData]);

  // Default to the latest year if available, else "All"
  const [year, setYear] = useState(
    years.length ? years[0] : "All"
  );

  // Data filtered by selected year (or all)
  const dataByYear = useMemo(() => {
    if (year === "All") return chartData;
    return chartData.filter((d) => getYear(d.date) === year);
  }, [chartData, year]);

  // --- Series toggles ---
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
      {/* Year chips row */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        {years.map((y) => (
          <Chip key={y} active={year === y} onClick={() => setYear(y)}>
            {y}
          </Chip>
        ))}
        {/* Optional "All" chip when multiple years exist */}
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
          onClick={() => setShow((s) => ({ ...s, clarity_pct: !s.clarity_pct }))}
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
            data={dataByYear}
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
              allowDecimals
              tickFormatter={fmtNDVI}
              label={{ value: yLeftLabel, angle: -90, position: "insideLeft" }}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 12 }}
              domain={rightDomain}
              allowDecimals
              tickFormatter={fmtNum2}
            />
            <Tooltip content={<HistoryTooltip />} />
            <Legend />
            {/* Brush removed */}

            {show.ndvi && (
              <Line
                type="monotone"
                dataKey="ndvi"
                yAxisId="left"
                name="NDVI"
                dot={false}
                strokeWidth={2}
                stroke={COLORS.ndvi}
                connectNulls
              />
            )}
            {show.temperature_deg_c && (
              <Line
                type="monotone"
                dataKey="temperature_deg_c"
                yAxisId="right"
                name="Temp (°C)"
                dot={false}
                strokeWidth={1.5}
                stroke={COLORS.temperature_deg_c}
                connectNulls
              />
            )}
            {show.wind_speed_mps && (
              <Line
                type="monotone"
                dataKey="wind_speed_mps"
                yAxisId="right"
                name="Wind (m/s)"
                dot={false}
                strokeWidth={1.5}
                stroke={COLORS.wind_speed_mps}
                connectNulls
              />
            )}
            {show.cloudcover_pct && (
              <Line
                type="monotone"
                dataKey="cloudcover_pct"
                yAxisId="right"
                name="Cloud (%)"
                dot={false}
                strokeWidth={1.5}
                stroke={COLORS.cloudcover_pct}
                connectNulls
              />
            )}
            {show.clarity_pct && (
              <Line
                type="monotone"
                dataKey="clarity_pct"
                yAxisId="right"
                name="Sun (%)"
                dot={false}
                strokeWidth={1.5}
                stroke={COLORS.clarity_pct}
                connectNulls
              />
            )}
            {show.humidity_pct && (
              <Line
                type="monotone"
                dataKey="humidity_pct"
                yAxisId="right"
                name="Humidity (%)"
                dot={false}
                strokeWidth={1.5}
                stroke={COLORS.humidity_pct}
                connectNulls
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

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

// ===== helpers =====

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
  // NDVI in [0,1] — show 2 digits
  return Number(v).toFixed(2).replace(/\.?0+$/,"");
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
    if (!(d instanceof Date) || Number.isNaN(d.getTime())) return String(v ?? "");
    return d.toISOString().slice(0, 10);
  } catch {
    return String(v ?? "");
  }
}

function HistoryTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) return null;
  const map = Object.fromEntries(payload.map((p) => [p.dataKey, p.value]));
  return (
    <div className="rounded-md border bg-white/95 p-2 text-xs shadow">
      <div className="font-medium mb-1">{formatDate(label)}</div>
      {map.ndvi !== undefined && <Row k="NDVI" v={round(map.ndvi)} />}
      {map.temperature_deg_c !== undefined && (
        <Row k="Temp" v={`${round(map.temperature_deg_c)} °C`} />
      )}
      {map.wind_speed_mps !== undefined && (
        <Row k="Wind" v={`${round(map.wind_speed_mps)} m/s`} />
      )}
      {map.cloudcover_pct !== undefined && (
        <Row k="Cloud" v={`${round(map.cloudcover_pct)} %`} />
      )}
      {map.clarity_pct !== undefined && (
        <Row k="Sun" v={`${round(map.clarity_pct)} %`} />
      )}
      {map.humidity_pct !== undefined && (
        <Row k="Humidity" v={`${round(map.humidity_pct)} %`} />
      )}
      {map.cloud_cover !== undefined && (
        <Row k="HLS Cloud" v={`${round(map.cloud_cover)} %`} />
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
