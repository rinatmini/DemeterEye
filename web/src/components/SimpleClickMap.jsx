import React, { useState } from "react";

export default function SimpleClickMap({ coords, setCoords }) {
  // Minimal SVG pad to capture polygon points without external map deps.
  const [hover, setHover] = useState(null);
  const width = 600,
    height = 360,
    padding = 20;
  const polyPoints = coords.map(([y, x]) => `${x},${y}`).join(" ");

  const handleClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.round(
      ((e.clientX - rect.left) / rect.width) * (width - 2 * padding) + padding
    );
    const y = Math.round(
      ((e.clientY - rect.top) / rect.height) * (height - 2 * padding) + padding
    );
    setCoords([...coords, [y, x]]);
  };
  const undo = () => setCoords(coords.slice(0, -1));
  const clear = () => setCoords([]);
  const closeShape = () => {
    if (coords.length >= 3) setCoords([...coords, coords[0]]);
  };

  return (
    <div>
      <div className="flex gap-2 mb-2">
        <button
          onClick={undo}
          className="rounded-xl border px-2 py-1 text-sm"
          disabled={!coords.length}
        >
          Undo
        </button>
        <button
          onClick={clear}
          className="rounded-xl border px-2 py-1 text-sm"
          disabled={!coords.length}
        >
          Clear
        </button>
        <button
          onClick={closeShape}
          className="rounded-xl border px-2 py-1 text-sm"
          disabled={coords.length < 3}
        >
          Close shape
        </button>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-64 bg-gray-100 rounded-xl border"
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const x = Math.round(
            ((e.clientX - rect.left) / rect.width) * (width - 2 * padding) +
              padding
          );
          const y = Math.round(
            ((e.clientY - rect.top) / rect.height) * (height - 2 * padding) +
              padding
          );
          setHover([y, x]);
        }}
        onClick={handleClick}
      >
        <rect
          x={padding}
          y={padding}
          width={width - 2 * padding}
          height={height - 2 * padding}
          fill="#fff"
          stroke="#e5e7eb"
        />
        {coords.length >= 2 && (
          <polyline
            points={polyPoints}
            fill="rgba(16,185,129,0.12)"
            stroke="#10b981"
            strokeWidth={2}
          />
        )}
        {coords.map(([y, x], i) => (
          <circle key={i} cx={x} cy={y} r={4} fill="#10b981" />
        ))}
        {hover && <circle cx={hover[1]} cy={hover[0]} r={3} fill="#64748b" />}
      </svg>
      <div className="text-xs text-gray-600 mt-1">
        Swap this with react-leaflet for real map drawing in production.
      </div>
    </div>
  );
}
