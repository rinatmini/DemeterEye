// src/views/FieldDetails.jsx
import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Loader2, Map as MapIcon, Pencil, Save, X } from "lucide-react";
import { apiFetch } from "../lib/api";
import StatusPill from "../components/StatusPill.jsx";
import MetricsChart from "../components/MetricsChart.jsx";
import FieldDrawMap from "../components/FieldDrawMap.jsx";
import fieldSvg from "../assets/field.svg";
import { cropIcons } from "../constants/cropIcons.js";

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
  const CROP_OPTIONS = ["Potato", "Soybean", "Sugar Beet", "Tomato", "Wheat"];
  const [geometry, setGeometry] = useState(null);
  const [yields, setYields] = useState([]);
  const [err, setErr] = useState("");

  const token = localStorage.getItem("token");

  const crop = field?.meta?.crop;

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
      setYields(f.yields ?? []);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(); // eslint-disable-next-line
  }, [id]);

  const upload = async () => {
    try {
      const f = await apiFetch(`/api/fields/${id}`, { token });
      setField(f);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  // repeat every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => upload(), 10000);
    return () => clearInterval(interval);
  }, [id]);

  const history = useMemo(() => field?.history ?? [], [field]);

  const saveMeta = async () => {
    setErr("");
    setEditMeta(false);
    saveField();
  };

  const saveGeometry = async () => {
    setErr("");
    setEditGeom(false);
    saveField();
  };

  const saveField = async () => {
    try {
      const body = {
        name: meta.name,
        notes: meta.notes,
        crop: meta.crop,
        yields,
        geometry,
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
      let sx = 0,
        sy = 0;
      for (const [lon, lat] of ring) {
        sx += lon;
        sy += lat;
      }
      return [sy / ring.length, sx / ring.length];
    }
    if (geo.type === "MultiPolygon") {
      const ring = geo.coordinates?.[0]?.[0];
      if (!ring?.length) return fallback;
      let sx = 0,
        sy = 0;
      for (const [lon, lat] of ring) {
        sx += lon;
        sy += lat;
      }
      return [sy / ring.length, sx / ring.length];
    }
    return fallback;
  }

  const addYieldRow = () => {
    if (yields.length === 0) {
      setYields((p) => [
        ...p,
        { year: new Date().getFullYear(), valueTph: "", unit: "t/ha" },
      ]);
      return;
    }
    const prevYear = yields[yields.length - 1].year - 1;
    setYields((p) => [...p, { year: prevYear, valueTph: "", unit: "t/ha" }]);
  };

  return (
    <div className="p-6 space-y-4">
      <button className="text-emerald-600 text-sm" onClick={() => nav(-1)}>
        ← Back to list
      </button>

      {/* Header card (stays full-width) */}
      <div className="rounded-2xl border bg-white p-4">
        <div className="flex items-center justify-between">
          <div className="font-semibold">{field.name}</div>
          <StatusPill status={field.status} />
        </div>
        <div className="mt-1 text-sm text-gray-600 flex items-center gap-3">
          <img
            src={cropIcons[crop.toLowerCase()] || "/favicon.svg"}
            className="h-10 w-10"
          />
          <span>{field?.meta?.crop || "—"}</span>
          <span className="text-gray-300">•</span>
          <span title="Area">{field?.meta?.areaHa ?? "—"} ha</span>
        </div>
      </div>

      {/* FULL-WIDTH METRICS */}
      <div className="rounded-2xl border bg-white p-4 pb-8">
        <div className="mb-2 flex items-center gap-2">
          <span className="font-semibold">Metrics</span>
        </div>
        {field.status === "processing" ? (
          // Show SVG animation while metrics are being computed
          <div
            className="relative w-full min-h-[320px] flex flex-col items-center justify-center"
            aria-live="polite"
          >
            <img
              src={fieldSvg}
              alt="Processing metrics animation"
              className="mx-auto w-full max-w-[700px] select-none pointer-events-none"
            />
            <span className="mt-2 text-sm text-gray-500">
              The metrics are being calculated...
            </span>
          </div>
        ) : (
          // Ready -> show the chart
          <MetricsChart history={history} />
        )}
      </div>

      {/* BELOW: GRID with Map (left) and Sidebar (right) */}
      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        {/* LEFT: Map card */}
        <div className="rounded-2xl border bg-white p-4 self-start">
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
                  <dt>Blooming peak</dt>
                  <dd>{field.forecast.ndviPeak ?? "—"}</dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt>Blooming start at</dt>
                  <dd>{field.forecast.ndviStartAt?.slice?.(0, 10) ?? "—"}</dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt>Blooming peak at</dt>
                  <dd>{field.forecast.ndviPeakAt?.slice?.(0, 10) ?? "—"}</dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt>Blooming end at</dt>
                  <dd>{field.forecast.ndviEndAt?.slice?.(0, 10) ?? "—"}</dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt>Blooming confidence</dt>
                  <dd>
                    {field.forecast.ndviConfidence != null
                      ? Math.round(field.forecast.ndviConfidence * 100) + "%"
                      : "—"}
                  </dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt>NDVI model</dt>
                  <dd>{field.forecast.ndviModel ?? "—"}</dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt>Yield</dt>
                  <dd>{field.forecast.yieldTph ?? "—"} t/ha</dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt>Confidence yield</dt>
                  <dd>
                    {field.forecast.yieldConfidence != null
                      ? Math.round(field.forecast.yieldConfidence * 100) + "%"
                      : "—"}
                  </dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt>Yield model</dt>
                  <dd>{field.forecast.yieldModel ?? "—"}</dd>
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
                {/* {field.photo && (
                  <img
                    src={field.photo}
                    alt=""
                    className="w-full rounded-xl object-cover max-h-48"
                  />
                )} */}
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
              <div className="space-y-3">
                <input
                  className="w-full rounded-xl border px-3 py-2"
                  placeholder="Name"
                  value={meta.name}
                  onChange={(e) =>
                    setMeta((m) => ({ ...m, name: e.target.value }))
                  }
                />
                <select
                  className="w-full rounded-xl border px-3 py-2 bg-white"
                  value={meta.crop}
                  onChange={(e) =>
                    setMeta((m) => ({ ...m, crop: e.target.value }))
                  }
                >
                  <option value="">Select crop…</option>
                  {CROP_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
                <div>
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

                {/* Editable yield table */}
                <div>
                  <div className="font-medium mb-1">Yield history</div>
                  <table className="w-full text-sm">
                    <thead className="text-gray-500">
                      <tr>
                        <th className="text-left py-1 w-24">Year</th>
                        <th className="text-right py-1 w-28">Value</th>
                        <th className="text-right py-1 w-24">Unit</th>
                        <th className="py-1 w-16"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {yields.map((y, i) => (
                        <tr key={i} className="border-t">
                          <td className="py-1">
                            <input
                              type="number"
                              className="w-full rounded border px-2 py-1 no-spinners"
                              value={y.year ?? ""}
                              onChange={(e) => {
                                const v = Number(e.target.value);
                                setYields((arr) =>
                                  arr.map((it, idx) =>
                                    idx === i ? { ...it, year: v } : it
                                  )
                                );
                              }}
                            />
                          </td>
                          <td className="py-1 text-right">
                            <input
                              type="number"
                              step="0.01"
                              className="w-full rounded border px-2 py-1 text-right no-spinners"
                              value={y.valueTph ?? ""}
                              onChange={(e) => {
                                const v =
                                  e.target.value === ""
                                    ? null
                                    : Number(e.target.value);
                                setYields((arr) =>
                                  arr.map((it, idx) =>
                                    idx === i ? { ...it, valueTph: v } : it
                                  )
                                );
                              }}
                            />
                          </td>
                          <td className="py-1 text-right">
                            <select
                              className="col-span-3 rounded-xl border px-3 py-2"
                              value={y.unit || "t/ha"}
                              onChange={(e) =>
                                setYields((arr) =>
                                  arr.map((it, idx) =>
                                    idx === i
                                      ? { ...it, unit: e.target.value }
                                      : it
                                  )
                                )
                              }
                            >
                              <option value="t/ha">t/ha</option>
                              <option value="lb/bu">lb/bu</option>
                            </select>
                          </td>
                          <td className="py-1 text-right">
                            <button
                              className="text-sm text-rose-600"
                              onClick={() =>
                                setYields((arr) =>
                                  arr.filter((_, idx) => idx !== i)
                                )
                              }
                            >
                              Delete
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  <div className="pt-2">
                    <button
                      className="text-sm px-3 py-1 rounded-xl border"
                      onClick={addYieldRow}
                    >
                      + Add row
                    </button>
                  </div>
                </div>
              </div>
            )}
            {err && <div className="text-sm text-rose-600">{err}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
