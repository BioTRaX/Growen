<!-- NG-HEADER: Nombre de archivo: MEDIA.md -->
<!-- NG-HEADER: Ubicación: docs/features/MEDIA.md -->
<!-- NG-HEADER: Descripción: Guía de manejo y almacenamiento de archivos multimedia. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

Los uploads canónicos usan `/canonical-products/{id}/knowledge/upload`, se deduplican por hash dentro del producto y quedan bajo `PRIVATE_MEDIA_ROOT/canonical-knowledge`. Documentos, imágenes y videos son procesados por `knowledge_worker`; frames y transcripciones respetan límites `KNOWLEDGE_*`.
Media y galería de productos
============================

- Estáticos `/media/*` servidos únicamente desde `PUBLIC_MEDIA_ROOT` (fallback
  local a `MEDIA_ROOT`). Ventas, compras y conocimiento nunca se montan allí.
- Los adjuntos privados se obtienen mediante endpoints autenticados de su
  dominio. Compras exige `admin|colaborador`; Ventas y Conocimiento validan rol
  y pertenencia y responden `404` ante rutas inválidas o recursos ajenos.
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
PUBLIC_MEDIA_ROOT=./Imagenes
PRIVATE_MEDIA_ROOT=./Devs/PrivateMedia
REDIS_URL=redis://localhost:6379/0
CLAMAV_ENABLED=true
CLAMD_HOST=127.0.0.1
CLAMD_PORT=3310
WATERMARK_LOGO=./Imagenes/Logos/logo.png
```

## Migración segura de archivos privados

`scripts/migrate_private_media.py` opera en `--dry-run` por defecto. Copia
`sales`, `canonical-knowledge` y la raíz legacy `data/purchases` a la raíz
privada, calcula SHA-256 antes y después, aborta ante conflictos y nunca elimina
originales. Ejemplo de previsualización:

```powershell
.\.venv\Scripts\python.exe scripts/migrate_private_media.py --dry-run --public-root C:\GrowenMedia --private-root C:\GrowenPrivate --purchases-root C:\Growen\data\purchases
```

Repetir con `--apply` sólo durante una ventana autorizada. El rollback consiste
en restaurar las variables anteriores mientras los originales preservados sigan
disponibles; su eliminación requiere una autorización posterior y verificación
independiente del manifiesto.

- Exportación TiendaNegocio: no requiere variables adicionales; el XLSX se genera bajo demanda con `GET /stock/export-tiendanegocio.xlsx` reutilizando los filtros de Stock.

