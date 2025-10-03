// src/views/CreateField.jsx
import React, { useState, useEffect } from "react";
import area from "@turf/area";
import { polygon as turfPolygon, multiPolygon as turfMultiPolygon } from "@turf/helpers";
import { Loader2, Map as MapIcon } from "lucide-react";
import { apiFetch } from "../lib/api.js";
import FieldDrawMap from "../components/FieldDrawMap.jsx";

export default function CreateField({ token, onCancel, onCreated }) {
  const [name, setName] = useState("");
  const [areaHa, setArea] = useState("");             // value shown in input
  const [autoAreaHa, setAutoAreaHa] = useState();     // numeric computed ha
  const [autoCalcArea, setAutoCalcArea] = useState(true); // <-- NEW: checkbox state
  const [overrideArea, setOverrideArea] = useState(false);
  const [photo, setPhoto] = useState("");
  const [crop, setCrop] = useState("");
  const [notes, setNotes] = useState("");
  const [geometry, setGeometry] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Recalculate area when geometry changes
  useEffect(() => {
    if (!geometry) {
      setAutoAreaHa(undefined);
      if (autoCalcArea) setArea("");
      return;
    }
    try {
      let m2 = 0;
      if (geometry.type === "Polygon") {
        m2 = area(turfPolygon(geometry.coordinates));
      } else if (geometry.type === "MultiPolygon") {
        m2 = area(turfMultiPolygon(geometry.coordinates));
      }
      const ha = +(m2 / 10_000).toFixed(2);
      setAutoAreaHa(ha);
      if (autoCalcArea) setArea(String(ha));
    } catch {
      /* ignore */
    }
  }, [geometry, autoCalcArea]);

  // Toggle auto-calc
  const toggleAutoCalc = (v) => {
    setAutoCalcArea(v);
    if (v) {
      setOverrideArea(false);
      setArea(autoAreaHa != null ? String(autoAreaHa) : "");
    }
  };

  const submit = async () => {
    setError("");
    if (!name || !geometry) {
      setError("Name and polygon are required");
      return;
    }
    setLoading(true);
    try {
      const body = {
        name,
        geometry,
        areaHa: areaHa ? Number(areaHa) : undefined,
        photo,
        notes,
        crop,
      };
      const res = await apiFetch("/api/fields", { method: "POST", body, token });
      onCreated(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      {/* LEFT: Map */}
      <div className="rounded-2xl border bg-white p-3">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold flex items-center gap-2">
            <MapIcon className="h-4 w-4" /> Draw field polygon
          </h3>
          <span className="text-xs text-gray-500">{geometry ? "Polygon ready" : "Draw a polygon"}</span>
        </div>
        <FieldDrawMap
          value={geometry}
          onChange={setGeometry}
          center={[50, 30]}
          zoom={14}
          className="w-full h-[70vh] rounded-xl border"
        />
      </div>
      <div className="flex flex-col gap-4">
        <div className="rounded-2xl border bg-white p-4 space-y-3">
          <h3 className="font-semibold">New Field</h3>

          <input
            className="w-full rounded-xl border px-3 py-2"
            placeholder="Field name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-3">
            <div className="relative">
              <input
                className={`w-full rounded-xl border px-3 py-2 pr-10 ${autoCalcArea ? "bg-gray-50 cursor-not-allowed" : ""}`}
                placeholder="Area (ha)"
                value={areaHa}
                disabled={autoCalcArea}
                onChange={(e) => {
                  setArea(e.target.value);
                  setOverrideArea(true);
                }}
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-500">ha</span>
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
            className="w-full rounded-xl border px-3 py-2"
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
            <button onClick={onCancel} className="rounded-xl border px-3 py-2">Cancel</button>
            <button
              disabled={loading}
              onClick={submit}
              className="rounded-xl bg-emerald-600 text-white px-3 py-2 hover:bg-emerald-700 inline-flex items-center gap-2"
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />} Create
            </button>
          </div>
        </div>

        <div className="rounded-2xl border bg-white p-4">
          <h3 className="font-semibold mb-2">Tips</h3>
          <ul className="list-disc pl-5 text-sm text-gray-700 space-y-1">
            <li>Draw a single polygon (no intersections). You can edit or delete it.</li>
            <li>Paste a Photo URL (S3/GCS) to show on the field card.</li>
            <li>After creation the processor will ingest history and set status to <code>ready</code>.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
