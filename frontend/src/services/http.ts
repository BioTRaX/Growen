// NG-HEADER: Nombre de archivo: http.ts
// NG-HEADER: Ubicación: frontend/src/services/http.ts
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import axios from "axios";

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
  return config;
});

export default http;
