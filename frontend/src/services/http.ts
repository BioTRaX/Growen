// NG-HEADER: Nombre de archivo: http.ts
// NG-HEADER: Ubicación: frontend/src/services/http.ts
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import axios from "axios";
import { diagAdd } from "../lib/corrStore";

// Compute a single API base bound to the current page hostname to avoid
// cookie/CSRF mismatches between 127.0.0.1 and localhost.
const host = typeof window !== "undefined" ? window.location.hostname : "127.0.0.1";
const fallback = `http://${host}:8000`;

function normalizeBase(url: string | undefined): string {
  try {
    if (!url) return fallback;
    const u = new URL(url);
    // Force same hostname as the page so cookies are shared
    u.hostname = host;
    // Ensure protocol if missing in env var (defensive)
    if (!u.protocol) u.protocol = "http:";
    return u.toString().replace(/\/$/, "");
  } catch {
    return fallback;
  }
}

export const baseURL = normalizeBase((import.meta as any).env?.VITE_API_URL);

const http = axios.create({
  baseURL,
  withCredentials: true,
});

// Adjuntar CSRF automáticamente en mutaciones
function getCookie(name: string): string | undefined {
  if (typeof document === "undefined") return undefined;
  const prefix = name + "=";
  const parts = document.cookie.split("; ");
  for (const p of parts) if (p.startsWith(prefix)) return decodeURIComponent(p.slice(prefix.length));
  return undefined;
}

http.interceptors.request.use((config) => {
  const method = (config.method || "get").toLowerCase();
  if (["post", "put", "patch", "delete"].includes(method)) {
    const csrf = getCookie("csrf_token");
    if (csrf) {
      config.headers = config.headers || {};
      (config.headers as any)["X-CSRF-Token"] = csrf;
    }
  }
  // mark start time for duration metrics
  (config as any)._start = Date.now();
  return config;
});

// Collect correlation-id and request diagnostics
http.interceptors.response.use(
  (response) => {
    try {
      const cfg: any = response.config || {};
      const started = cfg._start || Date.now();
      const dur = Date.now() - started;
      const cid = (response.headers && (response.headers["x-correlation-id"] || (response.headers as any)["X-Correlation-Id"])) as string | undefined;
      diagAdd({
        ts: new Date().toISOString(),
        method: (cfg.method || "GET").toUpperCase(),
        url: cfg.url || "",
        status: response.status,
        ms: dur,
        cid,
      });
    } catch {}
    return response;
  },
  (error) => {
    try {
      const resp = error.response;
      const cfg: any = (resp && resp.config) || error.config || {};
      const started = cfg._start || Date.now();
      const dur = Date.now() - started;
      const headers = (resp && resp.headers) || {};
      const cid = (headers["x-correlation-id"] || (headers as any)["X-Correlation-Id"]) as string | undefined;
      diagAdd({
        ts: new Date().toISOString(),
        method: (cfg.method || "GET").toUpperCase(),
        url: cfg.url || "",
        status: resp ? resp.status : 0,
        ms: dur,
        cid,
      });
    } catch {}
    return Promise.reject(error);
  }
);

export default http;
