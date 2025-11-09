<!-- NG-HEADER: Nombre de archivo: API_PRODUCTS.md -->
<!-- NG-HEADER: Ubicación: docs/API_PRODUCTS.md -->
<!-- NG-HEADER: Descripción: Documentación de endpoints de productos relevantes para UI. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Endpoints de productos (UI)

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
Metadatos de enriquecimiento IA:
- `enrichment_sources_url`: URL pública al archivo .txt con fuentes (si existe)
- `last_enriched_at`: fecha/hora UTC ISO cuando se realizó el último enriquecimiento (o null)
- `enriched_by`: id del usuario que ejecutó el enriquecimiento (o null)

UI: en la ficha de producto se muestra el `SKU` priorizando `canonical_sku` cuando está disponible; de lo contrario, se muestra el `sku_root` interno.

Campos técnicos expuestos (editables vía PATCH):
- `weight_kg`: número (kg) o null
- `height_cm`, `width_cm`, `depth_cm`: números (cm) o null
- `market_price_reference`: número (moneda, referencia de mercado) o null

---

## GET /stock/export.xlsx
Exporta un XLS con columnas: `NOMBRE DE PRODUCTO`, `PRECIO DE VENTA`, `CATEGORIA`, `SKU`.

Reglas de datos:
- Nombre y precio: si el item tiene canónico, se usa el nombre y precio del canónico. Si no, se usa la información del proveedor/interno.
- Categoría: preferir taxonomía del canónico. Si hay categoría y subcategoría, mostrar `Categoria > Subcategoria`. Si sólo hay categoría, `Categoria > Categoria`. Si no hay canónico, se usa el path del producto interno.
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
- Si no hay `OPENAI_API_KEY` y no corre un daemon de Ollama accesible (`OLLAMA_HOST`), la respuesta será un eco del prompt y `raw_ai_looks_json=false`. En ese caso el endpoint de enrich devolverá 502 porque la IA no entregó JSON válido.
- Si `AI_USE_WEB_SEARCH=1` pero el MCP web-search no está healthy, el enriquecimiento continúa sin resultados web (fallback, logs `mcp.web.*`).
- El prompt de enriquecimiento alienta a incluir un "Análisis de Mercado (AR$)" dentro de "Valor de mercado estimado" y a adjuntar "Fuentes" (URLs) para trazabilidad.


Estilos aplicados:
- Encabezado con fondo oscuro y texto claro, negrita.
- Nombres (columna 1) en negrita.
- Ajuste automático aproximado de ancho para la primera columna.

---

## GET /stock/export.csv
Exporta un CSV con las mismas columnas y reglas que el XLS: `NOMBRE DE PRODUCTO`, `PRECIO DE VENTA`, `CATEGORIA`, `SKU`.

Notas:
- Misma lógica de selección (canónico primero; fallback a proveedor/interno).
---

## POST /products/{id}/enrich
Enriquece un producto interno usando IA (OpenAI/Ollama vía AIRouter). Requiere CSRF y rol `admin` o `colaborador`.

Uso típico (desde la UI): botón “Enriquecer con IA” en la ficha del producto. Condiciones de visibilidad:
- El usuario debe tener permisos de edición (admin o colaborador).
- El producto debe tener `title`.

Validaciones y comportamiento:
- 404 si el producto no existe.
- 400 si el producto no tiene `title` definido.
- Invoca IA con un prompt que solicita un JSON con la clave “Descripción para Nice Grow” (y otros campos informativos como peso y dimensiones si se conocen).
- Actualiza `products.description_html` con “Descripción para Nice Grow”.
- Registra `AuditLog` con acción `enrich_ai` y campos afectados.

Parámetros:
- `force` (query, opcional): si es `true`, fuerza reescritura aunque ya exista contenido enriquecido y reemplaza el archivo `.txt` de fuentes (si lo hay). Se audita como `reenrich`.

Respuesta:
```
{ "status": "ok", "updated": true, "fields": ["description_html", ...], "sources_url": "/media/enrichment_logs/product_123_enrichment_20250101T120000Z.txt" }
```

Notas:
- Si la IA provee valores técnicos (peso, dimensiones, precio de mercado), el backend intentará mapearlos a los campos técnicos y persistirlos.
- Cuando la respuesta incluye “Fuentes”, se genera un `.txt` bajo `/media/enrichment_logs/` y se expone en `enrichment_sources_url`.
- Si `AI_USE_WEB_SEARCH=1` y `ai_allow_external=true`, el backend invoca opcionalmente el MCP `web_search` para anexar contexto de resultados (top N) al prompt. En la auditoría se incluyen `web_search_query` y `web_search_hits`.

---

## DELETE /products/{id}/enrichment
Elimina los datos enriquecidos por IA del producto. Requiere CSRF y rol `admin` o `colaborador`.

Acciones:
- Limpia `description_html`, `weight_kg`, `height_cm`, `width_cm`, `depth_cm`, `market_price_reference` y `enrichment_sources_url`.
- Limpia además metadatos `last_enriched_at` y `enriched_by`.
- Si existe archivo de fuentes (`enrichment_sources_url`), intenta borrarlo del storage.
- Registra `AuditLog` con acción `delete_enrichment` e incluye si el archivo fue eliminado.

Respuesta:
```
{ "status": "ok", "deleted": true }
```

---

## POST /products/enrich-multiple
Enriquece en lote (hasta 20) productos por sus IDs. Requiere CSRF y rol `admin` o `colaborador`.

Cuerpo:
```
{ "ids": [1,2,3], "force": false }
```

Reglas:
- Se ignoran productos sin `title`.
- Si `force=false` (por defecto), se omiten productos que ya tienen enriquecimiento (descripción o fuentes).
- Límite: 20 por lote para evitar bloqueos.

Respuesta:
```
{ "enriched": 6, "skipped": 2, "errors": [/* ids que fallaron */] }
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
Actualmente devuelve 501 (no implementado). Para habilitar PDF con estilo oscuro sugerimos integrar WeasyPrint o ReportLab y reutilizar la misma selección de datos del XLS/CSV.

Mientras tanto, utilice `/stock/export.xlsx` o `/stock/export.csv`.

## GET /catalog/next-seq
Devuelve la próxima secuencia por categoría para proponer SKUs canónicos.

Query:
- category_id (opcional): si se omite, cuenta global (o 1) según implementación.

Respuesta:
```
{ "category_id": 123, "next_seq": 24 }
```

Uso típico:
- La UI usa `next_seq` para previsualizar un SKU con la regla `XXX_####_YYY` (derivada de nombres de categoría/subcategoría). La generación y validación final ocurre en el backend al crear/editar el canónico.
