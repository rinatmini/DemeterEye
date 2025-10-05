import { LogOut } from "lucide-react";

export default function Topbar({ onLogout }) {
  return (
    <div className="sticky top-0 z-10 bg-white/80 backdrop-blur border-b">
      <div className="mx-auto max-w-6xl px-4 md:px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-2 font-semibold">
          <img src="/favicon.svg" className="h-16 w-16" />
          <span>DemeterEye</span>
        </div>
        <button
          onClick={onLogout}
          className="inline-flex items-center gap-2 rounded-xl border px-3 py-1.5 hover:bg-gray-50"
        >
          <LogOut className="h-4 w-4" /> Logout
        </button>
      </div>
    </div>
  );
}
