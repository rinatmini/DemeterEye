import React from "react";

export default function StatusPill({ status }) {
  const map = {
    ready: "bg-emerald-50 text-emerald-700 border-emerald-200",
    processing: "bg-amber-50 text-amber-700 border-amber-200",
    error: "bg-red-50 text-red-700 border-red-200",
  };
  const label = (status || "").toUpperCase();
  return (
    <span
      className={`text-xs border px-2 py-0.5 rounded-full ${
        map[status] || "bg-gray-50 text-gray-600 border-gray-200"
      }`}
    >
      {label || "—"}
    </span>
  );
}
