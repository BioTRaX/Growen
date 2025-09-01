Automatización de imágenes (Paso 2)
===================================

Scraper “Santa Planta”
- Whitelist: /shop/products/* y /shop/catalog*
- Rate-limit: ~1 req/s (burst 3; jitter 300–600ms)
- Selección de imagen: evitar -thumb/-mini y width<400; tomar la mayor
- Código: `services/scrapers/santaplanta.py`

Orquestador
- `services/media/orchestrator.py::ensure_product_image(product_id)`
  - Toma primera opción del proveedor; si falla y hay BING keys, usa Bing
  - Descarga (ClamAV), crea `image` + `image_versions` (original + derivados), marca `image_reviews.pending`

Jobs (Dramatiq + Redis)
- Broker: `services/jobs/__init__.py` (REDIS_URL)
- Actores: `services/jobs/images.py`
  - `crawl_product_missing_image(product_id)`
  - `crawl_catalog_missing_images()` → itera productos sin imágenes activas
  - `purge_soft_deleted(ttl_days)` → borra imágenes inactivas con antigüedad > TTL
- Ventana horaria (GMT-3) cuando `mode='window'`

Panel Admin
- Endpoints: `services/routers/image_jobs.py`
  - GET `/admin/image-jobs/status`
  - PUT `/admin/image-jobs/settings`
  - POST `/admin/image-jobs/trigger/crawl-missing`
  - POST `/admin/image-jobs/trigger/purge`
- Revisión: `GET /products/images/review`, `POST /products/images/{iid}/review/approve|reject`

Push Tiendanube
- Código: `services/integrations/tiendanube.py`
- Endpoints (en `images` router):
  - POST `/products/{pid}/images/push/tiendanube`
  - POST `/products/images/push/tiendanube/bulk`
- Rate-limit: 5/min con backoff simple
- Si no hay credenciales, modo dry-run almacena mapping stub

Notificaciones (opcional)
- Telegram: `services/notifications/telegram.py` (TELEGRAM_TOKEN/CHAT_ID)

Variables de entorno
```
REDIS_URL=redis://localhost:6379/0
TNUBE_API_TOKEN=
TNUBE_STORE_ID=
BING_API_KEY=
BING_IMAGE_SEARCH_URL=https://api.bing.microsoft.com/v7.0/images/search
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
```

