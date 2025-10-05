// src/views/FieldList.jsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";
import StatusPill from "../components/StatusPill.jsx";

export default function FieldList() {
  const nav = useNavigate();
  const [fields, setFields] = useState([]);
  const token = localStorage.getItem("token");

  useEffect(() => {
    (async () => {
      const data = await apiFetch("/api/fields", { token });
      setFields(data || []);
    })();
  }, []);

  const cardRing = (status) => {
    const s = (status || "").toLowerCase();
    if (s === "ready") return "ring-emerald-100 hover:ring-emerald-200";
    if (s === "processing") return "ring-amber-100 hover:ring-amber-200";
    if (s === "error") return "ring-rose-100 hover:ring-rose-200";
    return "ring-gray-100 hover:ring-gray-200";
  };

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold">My fields</h1>
        <button
          className="rounded-xl bg-emerald-600 text-white px-3 py-2 hover:bg-emerald-700"
          onClick={() => nav("/fields/new")}
        >
          New field
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {fields.map((f) => (
          <button
            key={f.id}
            onClick={() => nav(`/fields/${f.id}`)}
            className={`text-left rounded-2xl border bg-white p-4 ring-1 transition ${cardRing(
              f.status
            )}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="font-medium truncate">{f.name || "—"}</div>
              <StatusPill status={f.status} />
            </div>
            <div className="mt-1 text-sm text-gray-600">
              {f?.meta?.areaHa ?? "—"} ha • {f?.meta?.crop || "—"}
            </div>
            {/* можно показать миниатюру, если есть */}
            {f.photo && (
              <img
                src={f.photo}
                alt=""
                className="mt-3 h-24 w-full rounded-xl object-cover"
              />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
