<!-- NG-HEADER: Nombre de archivo: PRODUCTS_UI.md -->
<!-- NG-HEADER: Ubicación: docs/PRODUCTS_UI.md -->
<!-- NG-HEADER: Descripción: Documentación de la UI de Productos y creación/edición de canónicos. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# UI de Productos y Canónicos

## Listado de Productos
- Filtros disponibles:
  - Texto (`q`), Proveedor, Categoría, Stock (`gt:0`/`eq:0`), Recientes.
  - Tipo: `Todos | Canónicos | Proveedor` → mapea a `type=all|canonical|supplier` en `GET /products`.
- Fallback de datos en listado:
  - `name` y `precio_venta` se calculan en backend priorizando canónico (si existe) y sino proveedor.

- Campos adicionales desde backend (para mejorar la UI):
  - `canonical_sku`: SKU del producto canónico (si existe), o `null`.
  - `canonical_name`: Nombre del producto canónico (si existe), o `null`.
  - `first_variant_sku`: Primer SKU interno de variante del producto (si existe), útil como fallback visual.

  ### Nota sobre “Stock” y enlace de Precio de Venta

  - En la vista Stock (`/stock`) la columna “Precio venta” muestra el precio efectivo con la misma regla que el listado de Productos:
    - Si el producto está vinculado a un Canónico y éste tiene `sale_price`, se muestra ese valor.
    - Si no hay canónico o el canónico no tiene precio, se muestra el `current_sale_price` del `SupplierProduct` (proveedor) asociado.
  - La edición del precio desde Stock sigue esta lógica:
    - Con canónico: el lápiz edita `CanonicalProduct.sale_price` vía `PATCH /products-ex/products/{canonical_product_id}/sale-price`.
    - Sin canónico: el lápiz edita `SupplierProduct.current_sale_price` vía `PATCH /products-ex/supplier-items/{supplier_item_id}/sale-price`.
  - Exportar Stock (XLS/CSV/PDF) utiliza el mismo precio efectivo (canónico → proveedor) para la columna “PRECIO DE VENTA”.
- Exportar stock:
  - Botones en UI: “Descargar XLS”, “Descargar CSV” y “Exportar PDF”.
  - Endpoints: `GET /stock/export.xlsx`, `GET /stock/export.csv`, `GET /stock/export.pdf`.
  - Respetan los mismos filtros activos (texto, proveedor, categoría, stock) y el orden por defecto (`sort_by=updated_at&order=desc`).
  - El PDF se abre en una nueva pestaña y puede visualizarse o descargarse según el navegador (requiere dependencias de WeasyPrint en el backend; ver `docs/dependencies.md`).
  - XLSX: Encabezado con fondo oscuro y texto en blanco/negrita; la primera columna (“NOMBRE DE PRODUCTO”) se exporta en negrita por fila y se ajusta un ancho adecuado de forma automática.

## Detalle de Producto
- Visualización del SKU: si el producto está vinculado a un canónico y éste posee `sku_custom` (o `ng_sku`), se muestra ese SKU preferentemente; si no, se muestra `sku_root` del producto interno.
 - Acción “Enriquecer con IA”: botón visible sólo si el usuario tiene permisos de edición (admin/colaborador) y el producto tiene título. Al hacer clic ejecuta `POST /products/{id}/enrich`, muestra un toast de éxito/error y refresca los datos de la ficha. Estilo dark con borde fucsia (accentPink) y texto `#f5d0fe`.
 - Menú de acciones IA: junto al botón principal, la UI muestra un menú con:
   - “Reenriquecer (forzar)”: `POST /products/{id}/enrich?force=true` (reemplaza fuentes y reescribe descripción/campos técnicos si vienen en la respuesta).
   - “Borrar enriquecimiento”: `DELETE /products/{id}/enrichment` (limpia descripción, campos técnicos y fuentes asociadas).
 - Descripción enriquecida: se muestra en una card dedicada y puede editarse por Admin/Colab (persistencia vía `PATCH /products/{id}` con `description_html`).
 - Datos técnicos (Admin/Colab): `weight_kg`, `height_cm`, `width_cm`, `depth_cm`, `market_price_reference` con edición inline. La persistencia se realiza vía `PATCH /products/{id}` y se validan valores numéricos no negativos.
 - Fuentes consultadas: si `enrichment_sources_url` está presente en el producto, aparece el botón “Fuentes consultadas” que abre un modal con el contenido del `.txt` y enlace de descarga.
 - Metadatos de enriquecimiento: el backend expone `last_enriched_at` (ISO UTC) y `enriched_by` (id de usuario) para trazabilidad; la UI puede mostrarlos en una sección de “Actividad reciente” (opcional).

## Acciones masivas
- En el listado de Stock (`/stock`), al seleccionar múltiples productos aparece el botón “Enriquecer N producto(s) con IA)”.
  - Llama `POST /products/enrich-multiple` con `{ ids: [...], force?: boolean }` (límite de 20 IDs por solicitud).
  - La UI limpia la selección y refresca el listado al finalizar.

## Flags y comportamiento IA
- El enriquecimiento IA puede adjuntar resultados de búsqueda web (MCP) al prompt cuando:
  - `AI_USE_WEB_SEARCH=1` y `ai_allow_external=true` (ver configuración), y
  - Existe rol con permisos (admin/colaborador).
- Auditoría: se registran `web_search_query` y `web_search_hits` cuando la búsqueda web está activa.

## Alta/Edición de Producto Canónico
- Campos: `name`, `brand`, `sku_custom` (opcional), `category_id`, `subcategory_id`.
- Botón "Auto" de SKU:
  - Consulta `GET /catalog/next-seq?category_id=...` para proponer un SKU de forma `XXX_####_YYY`.
  - La UI muestra una vista previa; la generación y validación final se hacen en backend.
- Selección de categoría/subcategoría:
  - Subcategoría se filtra por la categoría elegida.
  - Botones "Nueva" abren modales para crear categorías en línea (padre nulo) o subcategorías (con padre).

### Creación mínima de producto interno (Sept 2025)
- El endpoint rápido de creación (catálogo interno) ahora acepta `supplier_id` como opcional.
- Si `supplier_id` se omite:
  - No se crea registro en `supplier_products` ni historial de precios asociado.
  - La respuesta omite campos específicos de proveedor (`supplier_item_id`).
- Si se provee `supplier_id`, se genera (cuando corresponde) el vínculo `SupplierProduct` básico y una entrada en historial de precios inicial.
- Razón del cambio: facilitar scripts y pruebas que requieren productos sin tener un proveedor cargado todavía.
- Implicación para UI: formularios de creación rápida pueden no requerir seleccionar proveedor; logic de downstream debe tolerar `supplier_id=null`.

### Comportamiento post-creación (refresco de lista)
- Al crear un Producto Canónico desde el listado embebido de Productos, la UI fuerza un refetch de la página 1 para evitar que la tabla quede vacía si ya estaba en la primera página.
- Esto preserva filtros y tipo de listado (Todos/Canónicos/Proveedor) y vuelve a mostrar resultados consistentes inmediatamente.

## Consistencia visual
- Encabezado con migas `Inicio › ...` y botones:
  - "Volver al inicio" → `PATHS.home`
  - "Volver" → `history.back()` (o `navigate(-1)`)
- Contenedores oscuros: usar `.panel` + paddings estándar.
- Enlaces de títulos de producto con clase `.product-title` (fucsia suave).

## Notas técnicas
- El componente `ProductsDrawer` soporta `mode="embedded"` para render sin overlay de pantalla completa.
- Los servicios del frontend (`products.ts`, `canonical.ts`) incluyen:
  - `searchProducts({... , type })` para el filtro.
  - `getNextSeq(category_id)` para la vista previa de SKU.
