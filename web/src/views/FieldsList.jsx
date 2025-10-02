import React, { useEffect, useState } from "react";
import { Plus, Map as MapIcon } from "lucide-react";
import { apiFetch } from "../lib/api.js";
import StatusPill from "../components/StatusPill.jsx";

export default function FieldsList({ token, onCreate, onOpen }) {
  const [fields, setFields] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch("/api/fields", { token });
      setFields(data ? data : []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">My Fields</h2>
        <button
          onClick={onCreate}
          className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 text-white px-3 py-2 hover:bg-emerald-700"
        >
          <Plus className="h-4 w-4" /> New Field
        </button>
      </div>
      {loading && <div className="text-gray-600">Loading…</div>}
      {error && <div className="text-red-600">{error}</div>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {fields.map((f) => (
          <div
            key={f.id}
            className="rounded-2xl border bg-white overflow-hidden hover:shadow-sm transition"
          >
            {f.photo ? (
              <img
                src={f.photo}
                alt="field"
                className="w-full h-36 object-cover"
              />
            ) : (
              <div className="w-full h-36 grid place-items-center bg-gradient-to-br from-emerald-50 to-white text-emerald-600">
                <MapIcon className="h-8 w-8" />
              </div>
            )}
            <div className="p-4">
              <div className="flex items-center justify-between">
                <div className="font-medium">{f.name}</div>
                <StatusPill status={f.status} />
              </div>
              {f?.meta?.areaHa && (
                <div className="text-sm text-gray-600 mt-1">
                  Area: {f.meta.areaHa} ha
                </div>
              )}
              {f?.meta?.crop && (
                <div className="text-sm text-gray-600">Crop: {f.meta.crop}</div>
              )}
              <div className="mt-3 flex justify-end">
                <button
                  onClick={() => onOpen(f)}
                  className="text-emerald-700 hover:underline"
                >
                  Open
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
