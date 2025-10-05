import { buildUrl } from "./config.js";
import { getToken } from "./auth.js";

export async function apiFetch(path, { method = "GET", body, token } = {}) {
  const t = token ?? getToken();
  const res = await fetch(buildUrl(path), {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(t ? { Authorization: `Bearer ${t}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  const raw = await res.text();
  if (!res.ok) {
    const err = new Error(raw?.message || res.statusText);
    err.status = res.status;
    err.body = raw;
    throw err;
  }

  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}
