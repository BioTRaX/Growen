Lightweight Startup and On-Demand Services
==========================================

Goals
- Fast TTFB for core: Login, Home/Chat, Productos (lista), Stock (vista), Compras (listado).
- Heavy services start on demand: PDF import (OCR), Playwright/Chromium crawler, image processing, Dramatiq/Redis, Scheduler, Tiendanube, Notifier.

Backend
- Service Registry tables: `services`, `service_logs`, `startup_metrics` (see migration 20250904_services_registry).
- Orchestrator: `services/orchestrator.py` tries `docker compose` else falls back to a lazy in-process registry.
- Admin API: `services/routers/services_admin.py` exposes:
  - POST `/admin/services/{name}/start|stop|panic-stop`
  - GET `/admin/services` and `/admin/services/{name}/status|logs`
- Startup metrics: first request records `ttfb_ms` and `app_ready_ms` in `startup_metrics`.

Health / Doctor
- `/health/optional` checks optional Python deps.
- `tools/doctor.py` now checks OCR/PDF system tools (ghostscript, qpdf, tesseract) and pip deps (ocrmypdf, rapidfuzz).

Frontend (guidelines)
- Add a “Servicios” panel (Admin) to start/stop and tail logs via the new endpoints.
- Use React.lazy/Suspense for heavy pages (PDF import, Playwright panel, gallery) and dynamic imports for helpers.

Dev
- To prefer lazy fallback (no Docker), set `SERVICES_FALLBACK_LAZY=true` and skip mounting docker.sock.
- For OCR completeness on Windows install: `tesseract`, `ghostscript`, `qpdf`. See README.

