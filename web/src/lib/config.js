const API_BASE_RAW =
  import.meta.env.VITE_API_BASE ?? import.meta.env.VITE_API_URL ?? "";
const API_BASE = (API_BASE_RAW || "").replace(/\/+$/, "");
export const buildUrl = (path) => (API_BASE ? `${API_BASE}${path}` : path);