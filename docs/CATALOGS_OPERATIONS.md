<!-- NG-HEADER: Nombre de archivo: CATALOGS_OPERATIONS.md -->
<!-- NG-HEADER: Ubicación: docs/CATALOGS_OPERATIONS.md -->
<!-- NG-HEADER: Descripción: Operación de catálogos: locks, diagnóstico, limpieza, descargas -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

Operación de Catálogos (PDF)
============================

Contexto
- Los catálogos se generan bajo `/catalogs/generate` y se almacenan en `./catalogos/` como `catalog_YYYYMMDD_HHMMSS.pdf`.
- Existe un alias `ultimo_catalogo.pdf` que apunta al último generado (symlink si el SO lo permite, o copia).
- Durante la generación se mantiene un flag en memoria para evitar ejecuciones concurrentes.

Diagnóstico rápido
- Estado: `GET /catalogs/diagnostics/status` devuelve `{ active_generation, detail_logs, summaries }`.
- Configuración: `GET /catalogs/diagnostics/config` devuelve `{ lock_timeout_s, source }`.
- Logs detallados: `GET /catalogs/diagnostics/log/{id}` lee `logs/catalogs/detail/catalog_{id}.log`.
- Resúmenes: `GET /catalogs/diagnostics/summaries?limit=20`.

Desbloqueo manual (lock)
- En caso de que una generación falle y deje el flag activo, usar:
  - `POST /catalogs/diagnostics/unlock` (requiere rol admin y CSRF). Respuesta incluye el estado previo y el actual.
  - Alternativamente, reiniciar el servicio backend limpia el flag (es in-memory).

Descarga desde el Frontend
- La descarga de XLS de stock usa `GET /stock/export.xlsx` (sin prefijo `/api`).
- La visualización/descarga de PDF usa `GET /catalogs/latest` y `GET /catalogs/latest/download`.

Detalles del XLS de stock
- Columnas: NOMBRE DE PRODUCTO, PRECIO DE VENTA, CATEGORIA, SKU PROPIO.
- Reglas de datos:
  - NOMBRE: toma el nombre canónico si el producto está vinculado a un canónico; en caso contrario, usa el nombre interno.
  - PRECIO DE VENTA: prioriza `CanonicalProduct.sale_price`; si no hay o no está definido, usa `SupplierProduct.current_sale_price`.
  - CATEGORIA: prioriza subcategoría/categoría canónica si está disponible; si no, utiliza la categoría del producto interno.
  - SKU PROPIO: muestra el `canonical_sku` (sku_custom o ng_sku) si existe; si no, usa el primer `Variant.sku` del producto interno.
- Estilo aplicado:
  - Encabezado con fondo oscuro y texto blanco en negrita, centrado.
  - Cada celda de la columna de NOMBRE se exporta en negrita.
  - Ancho de la primera columna ajustado automáticamente en base al contenido (límite máximo aplicado para evitar anchuras excesivas).

Dependencias de sistema
- Para convertir HTML→PDF (WeasyPrint) en Windows puede no estar disponible; hay fallback textual (ReportLab) si falla.
- Recomendado para features de PDF/OCR avanzados: Ghostscript y QPDF en PATH.

Timeout de lock
- El lock de generación expira automáticamente luego de `CATALOG_LOCK_TIMEOUT` segundos (default 900 = 15 minutos).
- El valor puede configurarse por entorno (`CATALOG_LOCK_TIMEOUT`) y es visible en el UI (modal de Historial de catálogos).

Checklist de cambios
- Si se altera el flujo o rutas, actualizar este documento y `docs/FRONTEND_DEBUG.md`.

Notas
- La retención de catálogos se controla con `CATALOG_RETENTION` (0 = ilimitado).
