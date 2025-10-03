// src/views/FieldDetails.jsx
import React, { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Loader2, Map as MapIcon, Pencil, Save, X, Leaf } from "lucide-react";
import { apiFetch } from "../lib/api";
import StatusPill from "../components/StatusPill.jsx";
import MetricsChart from "../components/MetricsChart.jsx";
import FieldDrawMap from "../components/FieldDrawMap.jsx";

export default function FieldDetails() {
  const { id } = useParams();
  const nav = useNavigate();

  const [field, setField] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editMeta, setEditMeta] = useState(false);
  const [editGeom, setEditGeom] = useState(false);
  const [meta, setMeta] = useState({
    name: "",
    crop: "",
    photo: "",
    notes: "",
  });
  const [geometry, setGeometry] = useState(null);
  const [err, setErr] = useState("");

  const token = localStorage.getItem("token");

  const load = async () => {
    setLoading(true);
    try {
      const f = await apiFetch(`/api/fields/${id}`, { token });
      setField(f);
      setMeta({
        name: f.name || "",
        crop: f?.meta?.crop || "",
        photo: f.photo || "",
        notes: f?.meta?.notes || "",
      });
      setGeometry(f.geometry);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(); /* eslint-disable-next-line */
  }, [id]);

  const history = useMemo(() => field?.history ?? [], [field]);

  const saveMeta = async () => {
    setErr("");
    try {
      const body = {
        name: meta.name,
        geometry,
        areaHa: field?.meta?.areaHa,
        photo: meta.photo,
        notes: meta.notes,
        crop: meta.crop,
      };
      const f = await apiFetch(`/api/fields/${id}`, {
        method: "PUT",
        token,
        body,
      });
      setField(f);
      setEditMeta(false);
    } catch (e) {
      setErr(e.message);
    }
  };

  const saveGeometry = async () => {
    setErr("");
    try {
      const f = await apiFetch(`/api/fields/${id}`, {
        method: "PUT",
        token,
        body: { geometry },
      });
      setField(f);
      setEditGeom(false);
    } catch (e) {
      setErr(e.message);
    }
  };

  if (loading) {
    return (
      <div className="p-6 text-gray-600 flex items-center gap-2">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading…
      </div>
    );
  }
  if (!field)
    return <div className="p-6 text-red-600">{err || "Not found"}</div>;

  function centerFromGeometry(geo) {
    const fallback = [47.6062, -122.3321];
  
    if (!geo) return fallback;
  
    if (geo.type === "Point") {
      const [lon, lat] = geo.coordinates;
      return [lat, lon];
    }
  
    if (geo.type === "Polygon") {
      const ring = geo.coordinates?.[0];
      if (!ring?.length) return fallback;
      let sx = 0, sy = 0;
      for (const [lon, lat] of ring) { sx += lon; sy += lat; }
      return [sy / ring.length, sx / ring.length];
    }
  
    if (geo.type === "MultiPolygon") {
      const ring = geo.coordinates?.[0]?.[0];
      if (!ring?.length) return fallback;
      let sx = 0, sy = 0;
      for (const [lon, lat] of ring) { sx += lon; sy += lat; }
      return [sy / ring.length, sx / ring.length];
    }
  
    return fallback;
  }

  return (
    <div className="p-6 space-y-4">
      <button className="text-emerald-600 text-sm" onClick={() => nav(-1)}>
        ← Back to list
      </button>

      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        {/* LEFT: Chart + Map */}
        <div className="space-y-4">
          {/* Header card */}
          <div className="rounded-2xl border bg-white p-4">
            <div className="flex items-center justify-between">
              <div className="font-semibold">{field.name}</div>
              <StatusPill status={field.status} />
            </div>
            <div className="mt-1 text-sm text-gray-600 flex items-center gap-3">
              <Leaf className="h-4 w-4 text-emerald-600" />
              <span>{field?.meta?.crop || "—"}</span>
              <span className="text-gray-300">•</span>
              <span title="Area">{field?.meta?.areaHa ?? "—"} ha</span>
            </div>
          </div>

          {/* Chart card */}
          <div className="rounded-2xl border bg-white p-4 pb-8">
            <div className="mb-2 flex items-center gap-2">
              <span className="font-semibold">Metrics</span>
            </div>
            <MetricsChart history={history} />
          </div>

          {/* Map card */}
          <div className="rounded-2xl border bg-white p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-semibold flex items-center gap-2">
                <MapIcon className="h-4 w-4" /> Field geometry
              </span>
              {!editGeom ? (
                <button
                  className="text-sm text-emerald-600 hover:underline"
                  onClick={() => setEditGeom(true)}
                >
                  Edit geometry
                </button>
              ) : (
                <div className="flex gap-2">
                  <button
                    className="text-sm px-3 py-1 rounded-xl border"
                    onClick={() => {
                      setGeometry(field.geometry);
                      setEditGeom(false);
                    }}
                  >
                    <X className="inline h-3 w-3 mr-1" /> Cancel
                  </button>
                  <button
                    className="text-sm px-3 py-1 rounded-xl bg-emerald-600 text-white"
                    onClick={saveGeometry}
                  >
                    <Save className="inline h-3 w-3 mr-1" /> Save
                  </button>
                </div>
              )}
            </div>
            {geometry?.coordinates?.[0] && (
              <FieldDrawMap
                value={geometry}
                onChange={setGeometry}
                mode={editGeom ? "edit" : "view"}
                initialCenter={centerFromGeometry(geometry)}
                initialZoom={14}
                className="w-full h-[380px] rounded-xl border"
              />
            )}
          </div>
        </div>

        {/* RIGHT: Forecast + About */}
        <div className="space-y-4">
          {/* Forecast */}
          <div className="rounded-2xl border bg-white p-4">
            <div className="font-semibold mb-2">Forecast</div>
            {field.forecast ? (
              <dl className="text-sm">
                <div className="flex justify-between py-1">
                  <dt>Year</dt>
                  <dd>{field.forecast.year}</dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt>Yield</dt>
                  <dd>{field.forecast.yieldTph ?? "—"} t/ha</dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt>NDVI peak</dt>
                  <dd>{field.forecast.ndviPeak ?? "—"}</dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt>Peak at</dt>
                  <dd>{field.forecast.ndviPeakAt?.slice(0, 10) ?? "—"}</dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt>Confidence</dt>
                  <dd>
                    {field.forecast.confidence != null
                      ? Math.round(field.forecast.confidence * 100) + "%"
                      : "—"}
                  </dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt>Model</dt>
                  <dd>{field.forecast.model ?? "—"}</dd>
                </div>
              </dl>
            ) : (
              <div className="text-sm text-gray-500">No forecast yet.</div>
            )}
          </div>

          {/* About / edit meta */}
          <div className="rounded-2xl border bg-white p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="font-semibold">About field</div>
              {!editMeta ? (
                <button
                  className="text-sm text-emerald-600 hover:underline flex items-center gap-1"
                  onClick={() => setEditMeta(true)}
                >
                  <Pencil className="h-3 w-3" /> Edit
                </button>
              ) : (
                <div className="flex gap-2">
                  <button
                    className="text-sm px-3 py-1 rounded-xl border"
                    onClick={() => {
                      setEditMeta(false);
                      setMeta({
                        name: field.name,
                        crop: field?.meta?.crop || "",
                        photo: field.photo || "",
                        notes: field?.meta?.notes || "",
                      });
                    }}
                  >
                    <X className="inline h-3 w-3 mr-1" /> Cancel
                  </button>
                  <button
                    className="text-sm px-3 py-1 rounded-xl bg-emerald-600 text-white"
                    onClick={saveMeta}
                  >
                    <Save className="inline h-3 w-3 mr-1" /> Save
                  </button>
                </div>
              )}
            </div>

            {!editMeta ? (
              <>
                {field.photo && (
                  <img
                    src={field.photo}
                    alt=""
                    className="w-full rounded-xl object-cover max-h-48"
                  />
                )}
                <dl className="text-sm">
                  <div className="flex justify-between py-1">
                    <dt>Name</dt>
                    <dd>{field.name}</dd>
                  </div>
                  <div className="flex justify-between py-1">
                    <dt>Crop</dt>
                    <dd>{field?.meta?.crop || "—"}</dd>
                  </div>
                  <div className="flex justify-between py-1">
                    <dt>Area</dt>
                    <dd>{field?.meta?.areaHa ?? "—"} ha</dd>
                  </div>
                  <div className="py-1">
                    <div className="text-gray-500">Notes</div>
                    <div>{field?.meta?.notes || "—"}</div>
                  </div>
                </dl>

                <div className="pt-3">
                  <div className="font-medium mb-1">Yield history</div>
                  {field.yields?.length ? (
                    <table className="w-full text-sm">
                      <thead className="text-gray-500">
                        <tr>
                          <th className="text-left py-1">Year</th>
                          <th className="text-right py-1">Value</th>
                          <th className="text-right py-1">Unit</th>
                        </tr>
                      </thead>
                      <tbody>
                        {field.yields.map((y, i) => (
                          <tr key={i} className="border-t">
                            <td className="py-1">{y.year}</td>
                            <td className="py-1 text-right">
                              {y.valueTph ?? "—"}
                            </td>
                            <td className="py-1 text-right">
                              {y.unit || "t/ha"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="text-sm text-gray-500">
                      No yield entries.
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="space-y-2">
                <input
                  className="w-full rounded-xl border px-3 py-2"
                  placeholder="Name"
                  value={meta.name}
                  onChange={(e) =>
                    setMeta((m) => ({ ...m, name: e.target.value }))
                  }
                />
                <input
                  className="w-full rounded-xl border px-3 py-2"
                  placeholder="Crop"
                  value={meta.crop}
                  onChange={(e) =>
                    setMeta((m) => ({ ...m, crop: e.target.value }))
                  }
                />
                <input
                  className="w-full rounded-xl border px-3 py-2"
                  placeholder="Photo URL"
                  value={meta.photo}
                  onChange={(e) =>
                    setMeta((m) => ({ ...m, photo: e.target.value }))
                  }
                />
                <textarea
                  className="w-full rounded-xl border px-3 py-2"
                  placeholder="Notes"
                  rows={4}
                  value={meta.notes}
                  onChange={(e) =>
                    setMeta((m) => ({ ...m, notes: e.target.value }))
                  }
                />
              </div>
            )}
            {err && <div className="text-sm text-rose-600">{err}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
