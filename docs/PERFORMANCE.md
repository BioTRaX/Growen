Lightweight Startup and On-Demand Services
==========================================

Goals
- Fast TTFB for core: Login, Home/Chat, Productos (lista), Stock (vista), Compras (listado).
- Heavy services start on demand: PDF import (OCR), Playwright/Chromium crawler, image processing, Dramatiq/Redis, Scheduler y Notifier. La exportación TiendaNegocio es síncrona (HTTP) y no requiere servicio dedicado.

Backend
- Service Registry tables: `services`, `service_logs`, `startup_metrics` (see migration 20250904_services_registry).
- Orchestrator: `services/orchestrator.py` tries `docker compose` else falls back to a lazy in-process registry.
- Admin API: `services/routers/services_admin.py` exposes:
  - POST `/admin/services/{name}/start|stop|panic-stop`
  - GET `/admin/services` and `/admin/services/{name}/status|logs`
- Startup metrics: first request records `ttfb_ms` and `app_ready_ms` in `startup_metrics`.

PostgreSQL pool y warmup (nuevo)
- El engine configura `pool_pre_ping=True` y respeta variables de entorno:
  - `PGCONNECT_TIMEOUT` (segundos, default 5) y `PGAPPNAME` para psycopg3.
  - `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT` para tunear el pool (opcionales).
- En el evento de `startup` de la API se ejecuta un warmup con `SELECT 1` y reintentos cortos:
  - `DB_WARMUP_ATTEMPTS` (default 4) y `DB_WARMUP_DELAY` en segundos (default 0.6).
  - Objetivo: evitar timeouts en la primera request (e.g., `/auth/login`) cuando la DB aún está estableciendo sockets.

Health / Doctor
- `/health/optional` checks optional Python deps.
- `tools/doctor.py` now checks OCR/PDF system tools (ghostscript, qpdf, tesseract) and pip deps (ocrmypdf, rapidfuzz).

Frontend (guidelines)
- Add a “Servicios” panel (Admin) to start/stop and tail logs via the new endpoints.
- Use React.lazy/Suspense for heavy pages (PDF import, Playwright panel, gallery) and dynamic imports for helpers.

Dev
- To prefer lazy fallback (no Docker), set `SERVICES_FALLBACK_LAZY=true` and skip mounting docker.sock.
- For OCR completeness on Windows install: `tesseract`, `ghostscript`, `qpdf`. See README.

