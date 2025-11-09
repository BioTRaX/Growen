<!-- NG-HEADER: Nombre de archivo: IMAGES_STEP2.md -->
<!-- NG-HEADER: Ubicación: docs/IMAGES_STEP2.md -->
<!-- NG-HEADER: Descripción: Notas de la segunda etapa del pipeline de imágenes. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
Images pipeline – Step 2

Env
- REDIS_URL=redis://localhost:6379/0
- TELEGRAM_TOKEN=<optional>
- TELEGRAM_CHAT_ID=<optional>
- IMAGE_MIN_SIZE=600 (default)

Workers
- Start Dramatiq worker (example):
  - python -m dramatiq workers.images --processes 1 --threads 1

Admin panel endpoints
- GET  /admin/image-jobs/status
- PUT  /admin/image-jobs/settings
- POST /admin/image-jobs/trigger/crawl-missing
- GET  /admin/image-jobs/logs?page=1&q=...

Scraper
- services/scrapers/santaplanta.py implements search_by_title, parse_product_page, crawl_catalog with a 1 rps limiter and thumbnail filtering.

Integración Tiendanube (REMOVIDA)
- La funcionalidad de push de imágenes a Tiendanube fue eliminada y reemplazada por una exportación a TiendaNegocio basada en XLS (`GET /stock/export-tiendanegocio.xlsx`) que respeta los mismos filtros activos en la vista de Stock. No se mantiene ya `services/integrations/tiendanube.py` ni los endpoints `/products/*/images/push/tiendanube`.

Review queue
- GET /products/images/review?status=pending
- POST /products/images/{id}/review/approve
- POST /products/images/{id}/review/reject {note}
