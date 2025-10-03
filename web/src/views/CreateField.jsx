import React, { useState, useEffect } from "react";
import area from "@turf/area";
import { useNavigate } from "react-router-dom";
import {
  polygon as turfPolygon,
  multiPolygon as turfMultiPolygon,
} from "@turf/helpers";
import { Loader2, Map as MapIcon, Plus, Trash2 } from "lucide-react";
import { apiFetch } from "../lib/api.js";
import FieldDrawMap from "../components/FieldDrawMap.jsx";

const DEFAULT_CENTER = [47.4554598, -122.2208032];
const DEFAULT_ZOOM = 14;

export default function CreateField() {
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [areaHa, setArea] = useState("");
  const [autoAreaHa, setAutoAreaHa] = useState();
  const [autoCalcArea, setAutoCalcArea] = useState(true);
  const [overrideArea, setOverrideArea] = useState(false);
  const [photo, setPhoto] = useState("");
  const [crop, setCrop] = useState("");
  const [notes, setNotes] = useState("");
  const [geometry, setGeometry] = useState(null);
  const [yields, setYields] = useState([
    { year: new Date().getFullYear(), valueTph: "", unit: "t/ha" },
  ]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const token = localStorage.getItem("token");

  // ===== area auto-calc =====
  useEffect(() => {
    if (!geometry) {
      setAutoAreaHa(undefined);
      if (autoCalcArea) setArea("");
      return;
    }
    try {
      let m2 = 0;
      if (geometry.type === "Polygon")
        m2 = area(turfPolygon(geometry.coordinates));
      else if (geometry.type === "MultiPolygon")
        m2 = area(turfMultiPolygon(geometry.coordinates));
      const ha = +(m2 / 10_000).toFixed(2);
      setAutoAreaHa(ha);
      if (autoCalcArea) setArea(String(ha));
    } catch {}
  }, [geometry, autoCalcArea]);

  const toggleAutoCalc = (v) => {
    setAutoCalcArea(v);
    if (v) {
      setOverrideArea(false);
      setArea(autoAreaHa != null ? String(autoAreaHa) : "");
    }
  };

  // ===== yields helpers =====
  const setYieldField = (idx, key, val) => {
    setYields((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], [key]: val };
      return next;
    });
  };
  const addYieldRow = () =>
    setYields((p) => [...p, { year: "", valueTph: "", unit: "t/ha" }]);
  const removeYieldRow = (idx) =>
    setYields((p) => p.filter((_, i) => i !== idx));

  const submit = async () => {
    setError("");
    if (!name || !geometry) {
      setError("Name and polygon are required");
      return;
    }
    // normalize yields: keep only rows with both year & value
    const normalizedYields = yields
      .map((y) => ({
        year: Number(y.year),
        valueTph: y.valueTph === "" ? undefined : Number(y.valueTph),
        unit: y.unit || "t/ha",
      }))
      .filter((y) => Number.isFinite(y.year) && Number.isFinite(y.valueTph));

    setLoading(true);
    try {
      const body = {
        name,
        geometry,
        areaHa: areaHa ? Number(areaHa) : undefined,
        photo,
        notes,
        crop,
        yields: normalizedYields,
      };
      const res = await apiFetch("/api/fields", {
        method: "POST",
        body,
        token,
      });
      nav(`/fields/${res.id}`, { replace: true });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const onCancel = () => {
    nav("/fields");
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      {/* LEFT: Map + tips */}
      <div className="flex flex-col gap-4">

        <div className="rounded-2xl border bg-white p-3">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-semibold flex items-center gap-2">
              <MapIcon className="h-4 w-4" /> Draw field polygon
            </h3>
            <span className="text-xs text-gray-500">
              {geometry ? "Polygon ready" : "Draw a polygon"}
            </span>
          </div>
          <FieldDrawMap
            mode="draw"
            value={geometry}
            onChange={setGeometry}
            initialCenter={DEFAULT_CENTER}
            initialZoom={DEFAULT_ZOOM}
            className="w-full h-[70vh] rounded-xl border"
          />
        </div>

        <div className="rounded-2xl border bg-white p-4">
          <h3 className="font-semibold mb-2">Tips</h3>
          <ul className="list-disc pl-5 text-sm text-gray-700 space-y-1">
            <li>
              Draw a single polygon (no intersections). You can edit or delete
              it.
            </li>
            <li>
              After creation the processor will ingest history and set status to{" "}
              <code>ready</code>.
            </li>
          </ul>
        </div>
      </div>

      {/* RIGHT: form */}
      <div className="flex flex-col gap-4">
        <div className="rounded-2xl border bg-white p-4 space-y-3">
          <h3 className="font-semibold">New Field</h3>

          <input
            className="w-full rounded-xl border px-3 py-2"
            placeholder="Field name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />

          {/* Area + auto-calc */}
          <div className="grid grid-cols-2 gap-3">
            <div className="relative">
              <input
                className={`w-full rounded-xl border px-3 py-2 pr-10 ${
                  autoCalcArea ? "bg-gray-50 cursor-not-allowed" : ""
                }`}
                placeholder="Area (ha)"
                value={areaHa}
                disabled={autoCalcArea}
                onChange={(e) => {
                  setArea(e.target.value);
                  setOverrideArea(true);
                }}
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-500">
                ha
              </span>
            </div>
            <label className="flex items-center gap-2 text-sm select-none">
              <input
                type="checkbox"
                className="h-4 w-4 accent-emerald-600"
                checked={autoCalcArea}
                onChange={(e) => toggleAutoCalc(e.target.checked)}
              />
              Auto-calc
            </label>
          </div>

          <input
            className="rounded-xl border px-3 py-2"
            placeholder="Crop"
            value={crop}
            onChange={(e) => setCrop(e.target.value)}
          />

          <input
            className="w-full rounded-xl border px-3 py-2"
            placeholder="Photo URL"
            value={photo}
            onChange={(e) => setPhoto(e.target.value)}
          />

          <textarea
            className="w-full rounded-xl border px-3 py-2"
            placeholder="Notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />

          {/* Yields section */}
          <div className="pt-2">
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-medium">Yields (per year)</h4>
              <button
                type="button"
                onClick={addYieldRow}
                className="inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-sm hover:bg-gray-50"
              >
                <Plus className="h-4 w-4" /> Add row
              </button>
            </div>

            <div className="space-y-2">
              {yields.map((y, idx) => (
                <div key={idx} className="grid grid-cols-12 gap-2 items-center">
                  <input
                    className="col-span-3 rounded-xl border px-3 py-2 no-spinners"
                    type="number"
                    placeholder="Year"
                    value={y.year}
                    onChange={(e) => setYieldField(idx, "year", e.target.value)}
                  />
                  <input
                    className="col-span-4 rounded-xl border px-3 py-2 no-spinners"
                    type="number"
                    step="0.01"
                    placeholder="Value"
                    value={y.valueTph}
                    onChange={(e) =>
                      setYieldField(idx, "valueTph", e.target.value)
                    }
                  />
                  <select
                    className="col-span-3 rounded-xl border px-3 py-2"
                    value={y.unit || "t/ha"}
                    onChange={(e) => setYieldField(idx, "unit", e.target.value)}
                  >
                    <option value="t/ha">t/ha</option>
                    <option value="lb/bu">lb/bu</option>
                  </select>
                  <button
                    type="button"
                    onClick={() => removeYieldRow(idx)}
                    className="col-span-2 inline-flex justify-center rounded-xl border px-2 py-2 hover:bg-red-50 text-red-600"
                    title="Remove row"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {geometry && (
            <details className="text-xs text-gray-600">
              <summary className="cursor-pointer">GeoJSON preview</summary>
              <pre className="bg-gray-50 p-2 rounded-xl overflow-auto">
                {JSON.stringify(geometry, null, 2)}
              </pre>
            </details>
          )}

          {error && <div className="text-red-600 text-sm">{error}</div>}

          <div className="flex gap-2 justify-end">
            <button onClick={onCancel} className="rounded-xl border px-3 py-2">
              Cancel
            </button>
            <button
              disabled={loading}
              onClick={submit}
              className="rounded-xl bg-emerald-600 text-white px-3 py-2 hover:bg-emerald-700 inline-flex items-center gap-2"
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />} Create
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
