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
    throw new Error(`${res.status} ${res.statusText}: ${raw}`);
  }

  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}
