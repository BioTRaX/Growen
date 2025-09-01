<!-- NG-HEADER: Nombre de archivo: IMAGES_STEP2.md -->
<!-- NG-HEADER: Ubicación: docs/IMAGES_STEP2.md -->
<!-- NG-HEADER: Descripción: Pendiente de descripción -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
Images pipeline – Step 2

Env
- REDIS_URL=redis://localhost:6379/0
- TELEGRAM_TOKEN=<optional>
- TELEGRAM_CHAT_ID=<optional>
- TNUBE_API_TOKEN=<optional>
- TNUBE_STORE_ID=<optional>
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

Push Tiendanube
- services/integrations/tiendanube.py provides upload_product_images and bulk_upload with a naive 5/min limiter; real API wiring pending.

Review queue
- GET /products/images/review?status=pending
- POST /products/images/{id}/review/approve
- POST /products/images/{id}/review/reject {note}
