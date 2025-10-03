import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";

export default function FieldsList() {
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const nav = useNavigate();
  const token = localStorage.getItem("token");

  useEffect(() => {
    let st = true;
    (async () => {
      try {
        const data = await apiFetch("/api/fields", { token });
        if (st) setItems(data);
      } catch (e) {
        if (st) setErr(e.message);
      }
    })();
    return () => {
      st = false;
    };
  }, [token]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">My fields</h2>
        <button
          className="rounded-xl bg-emerald-600 text-white px-3 py-2 hover:bg-emerald-700"
          onClick={() => nav("/fields/new")}
        >
          New field
        </button>
      </div>

      {err && <div className="text-rose-600">{err}</div>}

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((f) => (
          <Link
            key={f.id}
            to={`/fields/${f.id}`}
            className="rounded-2xl border bg-white p-4 hover:shadow-sm"
          >
            <div className="font-medium">{f.name}</div>
            <div className="text-sm text-gray-600">
              {f?.meta?.areaHa ?? "—"} ha • {f?.meta?.crop || "—"}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
