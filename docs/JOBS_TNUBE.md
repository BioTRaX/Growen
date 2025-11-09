<!-- NG-HEADER: Nombre de archivo: JOBS_TNUBE.md -->
<!-- NG-HEADER: Ubicación: docs/JOBS_TNUBE.md -->
<!-- NG-HEADER: Descripción: Documentación de jobs y sincronización con Tiendanube. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
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

Exportación a TiendaNegocio (estado actual)
- La UI de Stock incorpora el botón **“Exportar a TiendaNegocio”** junto a las descargas XLS/CSV/PDF. Respeta los filtros vigentes (`q`, `supplier_id`, `category_id`, `stock`, ordenamiento).
- Endpoint: `GET /stock/export-tiendanegocio.xlsx` (roles colaborador/admin). Implementado en `services/routers/catalog.py::export_stock_tiendanegocio_xlsx`.
- El backend arma un workbook con las columnas exigidas por TiendaNegocio:
  1. SKU (OBLIGATORIO)
  2. Nombre del producto
  3. Precio
  4. Oferta
  5. Stock
  6. Visibilidad (Visible o Oculto)
  7. Descripción
  8. Peso en KG
  9. Alto en CM
  10. Ancho en CM
  11. Profundidad en CM
  12-17. Parejas de “Nombre/Opción de variante #1..#3” (vacías por ahora)
  18. Categorías > Subcategorías > … > Subcategorías
- Datos preferidos:
  - SKU canónico cuando existe, si no el primer SKU del proveedor.
  - Nombre y precio priorizando el canónico (`canonical_*`).
  - Stock `Product.stock`, visibilidad siempre “Visible” (puede cambiarse si se requiere ocultar sin stock).
  - Descripción HTML enriquecida (`description_html`) si está presente; campos técnicos (`weight_kg`, `height_cm`, `width_cm`, `depth_cm`) se dejan vacíos cuando no hay datos.
- El XLSX se transmite vía `StreamingResponse` con `Content-Disposition: attachment; filename=productos_tiendanegocio.xlsx`.
- Tests: `tests/test_export_tiendanegocio_xlsx.py` valida encabezados y valores básicos sobre SQLite en memoria.

Histórico Tiendanube (retirado)
- Se eliminó el cliente `services/integrations/tiendanube.py`, adapters y endpoints `/products/*/images/push/tiendanube(*)`.
- Las variables `TNUBE_API_TOKEN` y `TNUBE_STORE_ID` ya no son necesarias y fueron removidas de `.env.example`.
- Cualquier despliegue que aún tuviera credenciales o webhooks debe limpiarse (revocar tokens en la tienda y borrar jobs programados).

Notificaciones (opcional)
- Telegram: `services/notifications/telegram.py` (TELEGRAM_TOKEN/CHAT_ID)

Variables de entorno
```
REDIS_URL=redis://localhost:6379/0
BING_API_KEY=
BING_IMAGE_SEARCH_URL=https://api.bing.microsoft.com/v7.0/images/search
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
```

