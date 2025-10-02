// src/views/CreateField.jsx
import React, { useState } from "react";
import { Loader2, Map as MapIcon } from "lucide-react";
import { apiFetch } from "../lib/api.js";
import FieldDrawMap from "../components/FieldDrawMap.jsx";

export default function CreateField({ token, onCancel, onCreated }) {
  const [name, setName] = useState("");
  const [areaHa, setArea] = useState("");
  const [photo, setPhoto] = useState("");
  const [crop, setCrop] = useState("");
  const [notes, setNotes] = useState("");
  const [geometry, setGeometry] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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
      const res = await apiFetch("/api/fields", {
        method: "POST",
        body,
        token,
      });
      onCreated(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      {/* LEFT: Map only */}
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
          value={geometry}
          onChange={setGeometry}
          center={[50, 30]}
          zoom={14}
          className="w-full h-[70vh] rounded-xl border"
        />
      </div>

      {/* RIGHT: form + tips stacked */}
      <div className="flex flex-col gap-4">
        {/* form */}
        <div className="rounded-2xl border bg-white p-4 space-y-3">
          <h3 className="font-semibold">New Field</h3>
          <input
            className="w-full rounded-xl border px-3 py-2"
            placeholder="Field name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-3">
            <input
              className="rounded-xl border px-3 py-2"
              placeholder="Area (ha)"
              value={areaHa}
              onChange={(e) => setArea(e.target.value)}
            />
            <input
              className="rounded-xl border px-3 py-2"
              placeholder="Crop"
              value={crop}
              onChange={(e) => setCrop(e.target.value)}
            />
          </div>
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

        {/* tips */}
        <div className="rounded-2xl border bg-white p-4">
          <h3 className="font-semibold mb-2">Tips</h3>
          <ul className="list-disc pl-5 text-sm text-gray-700 space-y-1">
            <li>
              Draw a single polygon (no intersections). You can edit or delete
              it.
            </li>
            <li>Paste a Photo URL (S3/GCS) to show on the field card.</li>
            <li>
              After creation the processor will ingest history and set status to{" "}
              <code>ready</code>.
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
