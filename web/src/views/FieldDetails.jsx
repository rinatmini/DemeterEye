import React, { useEffect, useMemo, useState } from "react";
import HistoryChart from "../components/HistoryChart.jsx";
import { apiFetch } from "../lib/api.js";
import { Leaf, Map as MapIcon } from "lucide-react";

export default function FieldDetails({ token, field, onBack, onUpdated }) {
  const [f, setF] = useState(field);
  const [err, setErr] = useState("");

  useEffect(() => {
    setF(field);
  }, [field]);

  const refresh = async () => {
    try {
      const data = await apiFetch(`/api/fields/${f.id}`, { token });
      setF(data);
      onUpdated(data);
    } catch (e) {
      setErr(e.message);
    }
  };

  const history = useMemo(
    () =>
      (f?.history || []).map((d) => ({
        date: new Date(d.date).toISOString().slice(0, 10),
        ndvi: d.ndvi ?? null,
        t: d.temperature_deg_c ?? null,
        wind: d.wind_speed_mps ?? null,
        cloud: d.cloudcover_pct ?? d.cloud_cover ?? null,
        sun: d.clarity_pct ?? null,
      })),
    [f]
  );

  return (
    <div className="space-y-4">
      <button onClick={onBack} className="text-emerald-700 hover:underline">
        ← Back to list
      </button>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="md:col-span-2 rounded-2xl border bg-white p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="font-semibold">{f.name}</div>
            <StatusPill status={f.status} />
          </div>
          <div className="text-sm text-gray-600 mb-3 flex gap-4 flex-wrap">
            {f?.meta?.crop && (
              <span className="inline-flex items-center gap-1">
                <Leaf className="h-4 w-4" /> {f.meta.crop}
              </span>
            )}
            {f?.meta?.areaHa && (
              <span className="inline-flex items-center gap-1">
                <MapIcon className="h-4 w-4" /> {f.meta.areaHa} ha
              </span>
            )}
          </div>
          <div className="h-72">
            <HistoryChart data={history} />
          </div>
          {err && <div className="text-red-600 text-sm mt-2">{err}</div>}
          <div className="mt-3 flex gap-2">
            <button onClick={refresh} className="rounded-xl border px-3 py-2">
              Refresh
            </button>
          </div>
        </div>
        <div className="rounded-2xl border bg-white p-4 space-y-3">
          <h3 className="font-semibold">Forecast</h3>
          {f?.forecast ? (
            <div className="text-sm text-gray-700 space-y-1">
              <div>
                <b>Year:</b> {f.forecast.year}
              </div>
              {f.forecast.yieldTph != null && (
                <div>
                  <b>Yield:</b> {f.forecast.yieldTph} t/ha
                </div>
              )}
              {f.forecast.ndviPeak != null && (
                <div>
                  <b>NDVI peak:</b> {f.forecast.ndviPeak}
                </div>
              )}
              {f.forecast.ndviPeakAt && (
                <div>
                  <b>Peak at:</b>{" "}
                  {new Date(f.forecast.ndviPeakAt).toISOString().slice(0, 10)}
                </div>
              )}
              {f.forecast.confidence != null && (
                <div>
                  <b>Confidence:</b> {(f.forecast.confidence * 100).toFixed(0)}%
                </div>
              )}
              {f.forecast.model && (
                <div className="text-xs text-gray-500">
                  Model: {f.forecast.model}
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-gray-500">
              No forecast yet. Status will switch to <code>ready</code> once the
              processor uploads one.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
