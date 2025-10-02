import React, { useState } from "react";
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

export default function HistoryChart({ data }) {
  const [show, setShow] = useState({
    ndvi: true,
    t: true,
    wind: false,
    cloud: false,
    sun: false,
  });
  const yLeftLabel = show.ndvi ? "NDVI" : show.t ? "Temp (°C)" : "";

  return (
    <div className="h-full w-full">
      <div className="flex gap-2 text-xs mb-2 flex-wrap">
        <Toggle
          label="NDVI"
          on={show.ndvi}
          onClick={() => setShow((s) => ({ ...s, ndvi: !s.ndvi }))}
        />
        <Toggle
          label="Temp"
          on={show.t}
          onClick={() => setShow((s) => ({ ...s, t: !s.t }))}
        />
        <Toggle
          label="Wind"
          on={show.wind}
          onClick={() => setShow((s) => ({ ...s, wind: !s.wind }))}
        />
        <Toggle
          label="Cloud"
          on={show.cloud}
          onClick={() => setShow((s) => ({ ...s, cloud: !s.cloud }))}
        />
        <Toggle
          label="Sun"
          on={show.sun}
          onClick={() => setShow((s) => ({ ...s, sun: !s.sun }))}
        />
      </div>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 10, right: 20, left: 0, bottom: 10 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis
            yAxisId="left"
            tick={{ fontSize: 12 }}
            domain={[0, "auto"]}
            label={{ value: yLeftLabel, angle: -90, position: "insideLeft" }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fontSize: 12 }}
            domain={[0, "auto"]}
          />
          <Tooltip />
          <Legend />
          {show.ndvi && (
            <Line
              type="monotone"
              dataKey="ndvi"
              yAxisId="left"
              dot={false}
              strokeWidth={2}
            />
          )}
          {show.t && (
            <Line
              type="monotone"
              dataKey="t"
              yAxisId="right"
              dot={false}
              strokeWidth={1.5}
            />
          )}
          {show.wind && (
            <Line
              type="monotone"
              dataKey="wind"
              yAxisId="right"
              dot={false}
              strokeWidth={1.5}
            />
          )}
          {show.cloud && (
            <Line
              type="monotone"
              dataKey="cloud"
              yAxisId="right"
              dot={false}
              strokeWidth={1.5}
            />
          )}
          {show.sun && (
            <Line
              type="monotone"
              dataKey="sun"
              yAxisId="right"
              dot={false}
              strokeWidth={1.5}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
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
