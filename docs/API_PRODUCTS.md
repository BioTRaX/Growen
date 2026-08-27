<!-- NG-HEADER: Nombre de archivo: API_PRODUCTS.md -->
<!-- NG-HEADER: Ubicación: docs/API_PRODUCTS.md -->
<!-- NG-HEADER: Descripción: Documentación de endpoints de productos relevantes para UI. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Endpoints de productos (UI)

## Taxonomía tipada y tags (2026-07-18)

- `GET /categories` y `GET /categories/search` aceptan `kind=category|subcategory`.
- `POST /categories` recibe `{name, kind}`; `parent_id` se acepta temporalmente e infiere subcategoría si falta `kind`.
- `POST /products` y `PATCH /products/{id}` admiten `category_id` y `subcategory_id`; en altas individuales son opcionales. El alta también admite `tag_names`.
- `POST /canonical-products/batch-job` persiste `tag_names` por ítem y exige IDs cuyos tipos sean correctos, sin relación padre-hijo.
- La idempotencia devuelve el lote existente sin duplicarlo. Si ese lote está `FAILED` con cero ítems procesados, una nueva solicitud con el mismo `client_request_id` lo restablece a `QUEUED` y vuelve a despacharlo; esto recupera fallos previos de Redis sin crear otro lote.
- `GET /catalog/search` aplica AND entre términos y permite que cada término coincida por nombre, descripción, SKU o tag.
- Las mutaciones de tags viven bajo `/tags`, requieren `colaborador|admin` y CSRF; la lectura admite usuarios autenticados.

## GET /products
Lista de productos (ofertas de proveedores vinculadas a productos internos) con filtros.

Parámetros útiles:
- q, supplier_id, category_id, stock (ej: `gt:0` o `eq:0`), created_since_days, paginación.
- type: `all` (default) | `canonical` | `supplier`.

Comportamiento:
- Búsqueda (`q`) ahora coincide por: título interno (`products.title`), título del proveedor (`supplier_products.title`) y también por título canónico (`canonical_products.name`).
- El payload incluye campos auxiliares: `canonical_product_id`, `canonical_sale_price`, `canonical_name`, `canonical_sku` y `first_variant_sku`.
- Nota: el campo `name` corresponde al título interno del producto.
- Nuevo: `preferred_name` (canónico primero) para centralizar la preferencia canónica en el backend. La UI puede usar este campo directamente.
- Nuevo: `tags`: array de objetos `{ id: number, name: string }` con los tags asignados al producto.

Ejemplo:
`GET /products?type=canonical&stock=gt:0&page=1&page_size=50`

---

## GET /products/{id}
Detalle de un producto interno. Además de los campos básicos (`id`, `title`, `slug`, `stock`, `sku_root`, `description_html`, `category_path`, `images`), ahora incluye campos canónicos cuando existe una equivalencia y metadatos de enriquecimiento:

- `canonical_product_id`: id del canónico vinculado (o null)
- `canonical_sale_price`: precio de venta del canónico (si existe)
- `canonical_sku`: SKU canónico propio (formato XXX_####_YYY), si existe
- `canonical_ng_sku`: SKU NG-######
- `canonical_name`: nombre del canónico
- `preferred_title`: título preferido para mostrar en UI (si existe `product.title_canonical`, se usa; si no, `canonical_name`; como último recurso `title`)
Compatibilidad temporal de enriquecimiento IA:
- `enrichment_sources_url`: campo legacy de sólo lectura durante el rollback
  React; el contenido vigente vive en `CanonicalProduct` y Base de Conocimiento.
- `last_enriched_at`: fecha/hora UTC ISO cuando se realizó el último enriquecimiento (o null)
- `enriched_by`: id del usuario que ejecutó el enriquecimiento (o null)

UI: en la ficha de producto se muestra el `SKU` priorizando `canonical_sku` cuando está disponible; de lo contrario, se muestra el `sku_root` interno.

Campos técnicos expuestos (editables vía PATCH):
- `weight_kg`: número (kg) o null
- `height_cm`, `width_cm`, `depth_cm`: números (cm) o null
- `market_price_reference`: número (moneda, referencia de mercado) o null

Tags:
- `tags`: array de objetos `{ id: number, name: string }` con los tags asignados al producto.

---

## GET /stock/export.xlsx
Exporta un XLS con columnas: `NOMBRE DE PRODUCTO`, `PRECIO DE VENTA`, `CATEGORIA`, `SKU PROPIO`.

Reglas de datos:
- Nombre y precio: si el item tiene canónico, se usa el nombre y precio del canónico. Si no, se usa la información del proveedor/interno.
- Categoría: preferir taxonomía del canónico. Si hay categoría y subcategoría, mostrar `Categoria > Subcategoria`; si sólo existe una clasificación, se muestra una sola vez. Si no hay canónico, se usa la taxonomía del producto interno.
## GET /debug/enrich/{id}
Solo administradores. Endpoint de diagnóstico para el flujo de enriquecimiento IA. No persiste cambios.

Devuelve JSON con:
- `title`: título elegido (prioriza canónico si existe)
- `title_used`: alias de `title` para consumo de UI/diagnóstico
- `ai_provider_selected`: proveedor IA que se usaría según la política actual
- `web_search`: estado (habilitado/health/query/hits) del MCP de búsqueda web
- `prompt`: prompt generado (incluye contexto MCP cuando está disponible)
- `raw_ai_preview`: primera parte de la respuesta cruda de IA (con prefijo `openai:`/`ollama:` si aplica)
- `raw_ai_looks_json`: booleano indicando si la vista previa parsea como JSON

Uso típico: abrir la ficha del producto, y en otra pestaña consultar `/debug/enrich/{id}` para confirmar que el flujo está operativo (providers, flags, web-search) cuando el botón “Enriquecer con IA” no produce cambios.

Notas:
- Si Ollama o el modelo configurado no están accesibles, el proveedor falla cerrado; nunca devuelve el prompt como eco. El endpoint traduce el fallo a un código seguro sin exponer el prompt.
- Si `AI_USE_WEB_SEARCH=1` pero el MCP web-search no está healthy, el enriquecimiento continúa sin resultados web (fallback, logs `mcp.web.*`).
- El prompt de enriquecimiento alienta a incluir un "Análisis de Mercado (AR$)" dentro de "Valor de mercado estimado" y a adjuntar "Fuentes" (URLs) para trazabilidad.


Estilos aplicados:
- Encabezado con fondo oscuro y texto claro, negrita.
- Nombres (columna 1) en negrita.
- Ajuste automático aproximado de ancho para la primera columna.

---

## GET /stock/export.csv
Exporta un CSV con las mismas columnas y reglas que el XLS: `NOMBRE DE PRODUCTO`, `PRECIO DE VENTA`, `CATEGORIA`, `SKU PROPIO`.

Notas:
- Misma lógica de selección (canónico primero; fallback a proveedor/interno).
- Codificación UTF-8 con BOM para compatibilidad con Excel.
- Admite `q`, `supplier_id`, `category_id`, `stock`, `type`, `created_since_days`, `sort_by` y `order`.
---

## POST /products/{id}/enrich (adaptador legacy)
Adapta temporalmente una solicitud por `Product.id` al job canónico de Enrich.
No genera contenido directamente ni calcula precios de mercado. Requiere CSRF y
rol `admin` o `colaborador`.

Uso típico (desde la UI): botón “Enriquecer con IA” en la ficha del producto. Condiciones de visibilidad:
- El usuario debe tener permisos de edición (admin o colaborador).
- El producto debe tener `title`.

Validaciones y comportamiento:
- 404 si el producto no existe.
- 409 si el producto no tiene canónico.
- Crea o reutiliza un job en `/canonical-products/{id}/enrichment-jobs`.
- Devuelve `job_id`, `canonical_product_id` y `status_url`.

Parámetros:
- `force` (query, opcional): conserva el comportamiento de idempotencia del
  adaptador durante el fallback; las nuevas integraciones deben usar el job
  canónico y su `client_request_id`.

Respuesta compatible:
```
{ "status": "queued", "updated": false, "job_id": "...", "canonical_product_id": 18, "status_url": "/canonical-products/18/enrichment-jobs/..." }
```

Notas:
- El contenido nuevo se persiste sólo en el canónico y sus versiones/evidencias.
- Las fuentes se gestionan desde la Base de Conocimiento; no se genera un
  archivo `.txt` legacy.

---

## DELETE /products/{id}/enrichment (adaptador legacy)
Limpia el contenido del canónico vinculado y conserva una versión auditable.
Se mantiene sólo durante el ciclo de compatibilidad React.

Acciones:
- No modifica valores de mercado.
- Limpia el contenido canónico mediante una nueva revisión y auditoría.

Respuesta:
```
{ "status": "ok", "canonical_product_id": 18, "content_revision": 4, "cleared_fields": ["description_html"] }
```

---

## POST /products/enrich-multiple (adaptador legacy)
Adapta temporalmente IDs internos a jobs canónicos únicos. Requiere CSRF y rol
`admin` o `colaborador`.

Cuerpo:
```
{ "ids": [1,2,3], "force": false }
```

Reglas:
- Se omiten productos sin canónico.
- Los productos internos que apuntan al mismo canónico generan un único job.
- El contrato nuevo es `POST /canonical-products/enrichment-batches`.

Respuesta:
```
{ "status": "queued", "batch_id": "...", "jobs": [], "skipped": [] }
```

Auditoría:
- Registra `bulk_enrich` con meta `{ requested, enriched, skipped, errors, ids }`.

---

## PATCH /products/{id}
Actualiza campos del producto. Requiere CSRF y rol `admin` o `colaborador`.

Campos soportados (todos opcionales):
- `description_html`: string o null
- `category_id`: int o null (se valida existencia si no es null)
- `weight_kg`: number >= 0 o null
- `height_cm`: number >= 0 o null
- `width_cm`: number >= 0 o null
- `depth_cm`: number >= 0 o null
- `market_price_reference`: number >= 0 o null

Validaciones:
- Valores numéricos deben ser >= 0.
- `category_id` debe existir si se especifica.

Respuesta:
```
{ "status": "ok" }
```

- Mismos filtros que `/products` y `/stock/export.xlsx`.

---

## GET /stock/export.pdf
Genera `stock.pdf` mediante ReportLab en A4 horizontal, con encabezado oscuro, tabla paginada y las mismas filas/columnas que XLSX y CSV. No requiere WeasyPrint.

Admite `q`, `supplier_id`, `category_id`, `stock`, `type`, `created_since_days`, `sort_by` y `order`. Los roles permitidos son `cliente`, `proveedor`, `colaborador` y `admin`.

## PATCH /products/{id}/stock

Requiere `colaborador` o `admin` y CSRF. Acepta `{ "stock": 10.25, "expected_stock": 10.00 }`; ambos valores admiten hasta dos decimales. `expected_stock` es opcional para compatibilidad con React e intents.

La fila se bloquea hasta finalizar la transacción. Si el saldo leído cambió, responde 409 con `detail.message` y `detail.current_stock`, sin sobrescribir. Un ajuste exitoso crea exactamente un `StockLedger` con `source_type=manual_adjustment`, delta/saldo decimal y metadatos de valores anterior/nuevo y usuario, además del `AuditLog` correspondiente.

## /stock/shortages

`POST /stock/shortages`, `GET /stock/shortages` y `GET /stock/shortages/stats` requieren `colaborador` o `admin`; el POST también requiere CSRF global. La cantidad admite hasta dos decimales, el producto se bloquea al descontar y se permite saldo negativo con advertencia. No se incorpora conciliación en este corte.

## GET /catalog/next-seq
Devuelve una estimación no reservante de la próxima secuencia por categoría para clientes heredados.

Query:
- category_id (opcional): si se omite, cuenta global (o 1) según implementación.

Respuesta:
```
{ "category_id": 123, "next_seq": 24 }
```

Uso típico:
- React heredado puede usar `next_seq` para una vista previa con la regla `XXX_####_YYY`.
- Vue usa `POST /canonical-products/sku-preview`, que permite previsualizar todas las filas del lote sin reservar números.
- Ninguna vista previa debe persistirse como SKU definitivo. La asignación final ocurre en backend mediante `generate_canonical_sku()` dentro de la transacción de creación.

---

## Endpoints de Tags

### GET /tags
Lista todos los tags existentes, opcionalmente filtrados por búsqueda.

Query parameters:
- `q` (opcional): búsqueda por nombre (parcial, case-insensitive)

Respuesta:
```json
[
  { "id": 1, "name": "Orgánico" },
  { "id": 2, "name": "Floración" }
]
```

Requiere rol: `cliente`, `proveedor`, `colaborador` o `admin`.

---

### POST /tags
Crea un nuevo tag. Si ya existe un tag con el mismo nombre, retorna el existente.

Cuerpo:
```json
{ "name": "Orgánico" }
```

Respuesta:
```json
{ "id": 1, "name": "Orgánico" }
```

Requiere CSRF y rol: `colaborador` o `admin`.

---

### POST /tags/products/{product_id}/tags
Asigna tags a un producto. Crea los tags si no existen.

Cuerpo:
```json
{ "tag_names": ["Orgánico", "Floración"] }
```

Respuesta:
```json
{
  "product_id": 123,
  "assigned_tags": ["Orgánico", "Floración"],
  "new_assignments": ["Orgánico"]  // Tags que se crearon o asignaron por primera vez
}
```

Requiere CSRF y rol: `colaborador` o `admin`.

---

### DELETE /tags/products/{product_id}/tags/{tag_id}
Desvincula un tag de un producto.

Respuesta:
```json
{
  "product_id": 123,
  "tag_id": 1,
  "removed": true
}
```

Requiere CSRF y rol: `colaborador` o `admin`.

---

### POST /tags/products/bulk-tags
Asigna tags a múltiples productos a la vez.

Cuerpo:
```json
{
  "product_ids": [1, 2, 3],
  "tag_names": ["Orgánico", "Floración"]
}
```

Respuesta:
```json
{
  "product_ids": [1, 2, 3],
  "tag_names": ["Orgánico", "Floración"],
  "tags_assigned": 2,
  "new_relations_created": 5,
  "existing_relations_skipped": 1
}
```

Requiere CSRF y rol: `colaborador` o `admin`.

Notas:
- Si un tag no existe, se crea automáticamente.
- Si un producto ya tiene un tag asignado, se omite (no se duplica).
- Si algún producto no existe, se retorna 404 con la lista de IDs faltantes.
