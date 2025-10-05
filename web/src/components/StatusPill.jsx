/** Small colored pill for field status: processing | ready | error */
export default function StatusPill({ status }) {
  const map = {
    processing: {
      label: "Processing",
      cls: "bg-amber-100 text-amber-700 ring-amber-200",
    },
    ready: {
      label: "Ready",
      cls: "bg-emerald-100 text-emerald-700 ring-emerald-200",
    },
    error: {
      label: "Error",
      cls: "bg-rose-100 text-rose-700 ring-rose-200",
    },
  };
  const m = map[status] || {
    label: "Unknown",
    cls: "bg-gray-100 text-gray-700 ring-gray-200",
  };

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${m.cls}`}
      title={status}
    >
      {m.label}
    </span>
  );
}
