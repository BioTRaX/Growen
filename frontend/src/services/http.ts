import axios from "axios";
const http = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000",
  withCredentials: true,
});
http.interceptors.request.use((cfg) => {
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  if (m) {
    const headers = (cfg.headers ??= {} as any);
    headers["X-CSRF-Token"] = decodeURIComponent(m[1]);
  }
  return cfg;
});
export default http;
