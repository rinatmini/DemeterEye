import React from "react";
import {
  ResponsiveContainer,
  LineChart, Line,
  XAxis, YAxis, Tooltip, Legend,
  CartesianGrid,
} from "recharts";

const COLORS = {
  ndvi:  "#10b981", // emerald
  temp:  "#f59e0b", // amber
  wind:  "#3b82f6", // blue
  sun:   "#eab308", // yellow
  cloud: "#6b7280", // gray
};

export default function MetricsChart({ history = [], visible = ["ndvi","temp","wind","sun","cloud"] }) {
  const data = history.map(d => ({
    date: new Date(d.date).toISOString().slice(0,10),
    ndvi: d.ndvi ?? null,
    temp: d.temperature_deg_c ?? null,
    wind: d.wind_speed_mps ?? null,
    sun:  d.clarity_pct ?? null,
    cloud:d.cloudcover_pct ?? null,
  }));

  const show = (k) => visible.includes(k);

  return (
    <div className="w-full h-[340px]">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ left: 12, right: 24, top: 10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          {/* Y1 — NDVI (0..1) */}
          <YAxis yAxisId="y1" domain={[0,1]} tick={{ fontSize: 12 }} />
          {/* Y2 — всё остальное (авто) */}
          <YAxis yAxisId="y2" orientation="right" tick={{ fontSize: 12 }} />
          <Tooltip />
          <Legend />

          {show("ndvi")  && <Line yAxisId="y1" type="monotone" dataKey="ndvi" stroke={COLORS.ndvi} dot={false} strokeWidth={2} />}
          {show("temp")  && <Line yAxisId="y2" type="monotone" dataKey="temp" stroke={COLORS.temp} dot={false} />}
          {show("wind")  && <Line yAxisId="y2" type="monotone" dataKey="wind" stroke={COLORS.wind} dot={false} />}
          {show("sun")   && <Line yAxisId="y2" type="monotone" dataKey="sun" stroke={COLORS.sun} dot={false} />}
          {show("cloud") && <Line yAxisId="y2" type="monotone" dataKey="cloud" stroke={COLORS.cloud} dot={false} />}
        </LineChart>
      </ResponsiveContainer>
      <div className="mt-2 text-xs text-gray-500 px-1 leading-tight">
        Left axis: NDVI (0–1). Right axis: °C / m·s⁻¹ / %.
      </div>
    </div>
  );
}
