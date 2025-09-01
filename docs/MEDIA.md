Media y galería de productos
============================

- Estáticos `/media/*` servidos desde `MEDIA_ROOT` (por defecto `./Imagenes` o variable de entorno).
- Subida de imágenes y descarga por URL:
  - `POST /products/{pid}/images/upload` (multipart `file`)
  - `POST /products/{pid}/images/from-url` (body `{ url }`)
- Operaciones de galería:
  - `POST /products/{pid}/images/{iid}/set-primary`
  - `POST /products/{pid}/images/{iid}/lock`
  - `DELETE /products/{pid}/images/{iid}` (soft delete)
  - `POST /products/{pid}/images/reorder` (body `{ image_ids: [] }`)
- Procesos manuales:
  - `POST /products/{pid}/images/{iid}/process/remove-bg`
  - `POST /products/{pid}/images/{iid}/process/watermark`
- SEO ALT/Title:
  - `POST /products/{pid}/images/{iid}/seo/refresh`

Scraper “Santa Planta” y jobs Dramatiq cuentan con esqueletos para crawling y descarga asistida.
El panel Admin expone `/admin/image-jobs/*` para estado y configuración del job “imagenes_productos”.

Variables de entorno relevantes:

```
MEDIA_ROOT=./Imagenes
REDIS_URL=redis://localhost:6379/0
CLAMAV_ENABLED=true
CLAMD_HOST=127.0.0.1
CLAMD_PORT=3310
WATERMARK_LOGO=./Imagenes/Logos/logo.png
TNUBE_API_TOKEN=
TNUBE_STORE_ID=
```

