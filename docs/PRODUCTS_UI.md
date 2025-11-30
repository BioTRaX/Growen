<!-- NG-HEADER: Nombre de archivo: PRODUCTS_UI.md -->
<!-- NG-HEADER: Ubicación: docs/PRODUCTS_UI.md -->
<!-- NG-HEADER: Descripción: Documentación de la UI de Productos y creación/edición de canónicos. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# UI de Productos y Canónicos

# UI de Productos y Canónicos

## Listado de Productos

### Navegación y Paginación (Nov 2025)
- **Paginación integrada**: En la vista `/productos` (modo embedded del componente `ProductsDrawer`), se implementó un sistema de paginación similar al de `/stock`:
  - Botones "Anterior" y "Más" al pie del listado (clases `.btn-dark .btn-lg` para consistencia visual).
  - **Botón "Anterior"**: Vuelve a la primera página y hace scroll suave hacia arriba. Deshabilitado cuando `page === 1` o durante carga.
  - **Botón "Más"**: Carga la siguiente página de resultados. Deshabilitado cuando se han mostrado todos los productos (`items.length >= total`) o durante carga.
  - **Tamaño de página**: 50 productos por página (configurable vía `pageSize`).
  - **Mantenimiento de filtros**: Al cambiar de página, todos los filtros activos (texto, proveedor, categoría, stock, recientes, tipo) se preservan automáticamente.
  - **Indicador de progreso**: Se muestra "(Mostrando X de Y)" junto al contador de resultados para dar visibilidad del estado de carga.

- **Scroll único**: En modo embedded, el componente usa `overflowY: 'visible'` para eliminar el scroll interno de la tabla, dejando solo el scroll de la página principal. Esto resuelve el problema del "doble scroll vertical" que confundía la navegación.

- **Scroll horizontal**: Para columnas que no caben en el ancho de pantalla, la tabla implementa un scroll horizontal único y controlado (`overflowX: 'auto'`). El `minWidth` de la tabla se calcula como la suma de los anchos de todas las columnas visibles, garantizando que ninguna columna quede oculta.

### Filtros disponibles:
  - Texto (`q`), Proveedor, Categoría, Stock (`gt:0`/`eq:0`), Recientes.
  - Tipo: `Todos | Canónicos | Proveedor` → mapea a `type=all|canonical|supplier` en `GET /products`.
- Búsqueda por texto (`q`): coincide por título interno, título del proveedor y título canónico.
- Visualización de nombre en UI:
  - La UI usa el campo `preferred_name` del backend (canónico primero, título interno como fallback).
  - Esto simplifica la lógica del frontend y mantiene consistencia con enriquecimiento y catálogos.

- Campos adicionales desde backend (para mejorar la UI):
  - `canonical_sku`: SKU del producto canónico (si existe), o `null`.
  - `canonical_name`: Nombre del producto canónico (si existe), o `null`.
  - `first_variant_sku`: Primer SKU interno de variante del producto (si existe), útil como fallback visual.
  - `preferred_name`: Título preferido calculado por el backend (canónico → interno).

### Estilización de nombres de productos (Nov 2025)
- **Formato Title Case**: Los nombres de productos canónicos se muestran con estilización automática:
  - Cada palabra inicia con mayúscula inicial (Title Case).
  - Unidades de medida se preservan en mayúsculas: GR, KG, L, ML, CC, etc.
  - Acrónimos comunes en mayúsculas: LED, UV, NPK, PH, etc.
  - Conectores en español van en minúsculas: de, la, el, para, con, etc. (excepto al inicio).
- **Ejemplos**:
  - `"FEEDING BIO GROW (125 GR)"` → `"Feeding Bio Grow (125 GR)"`
  - `"ACEITE DE NEEM 250 ML"` → `"Aceite de Neem 250 ML"`
  - `"FERTILIZANTE NPK 20-20-20"` → `"Fertilizante NPK 20-20-20"`
- **Aplica en**: Vista de Stock, exports XLS, export TiendaNegocio, detalle de producto.
- **Implementación**: `db/text_utils.stylize_product_name()` (ver tests en `tests/test_text_utils.py`).

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
  - Nuevo: “Exportar a TiendaNegocio” (XLSX) exporta con la misma vista/filtros activos en el formato requerido por TiendaNegocio.
    - Endpoint: `GET /stock/export-tiendanegocio.xlsx` (roles: colaborador/admin).
    - Columnas: SKU, Nombre, Precio (precio efectivo canónico→proveedor), Oferta (vacío), Stock, Visibilidad (Visible), Descripción, Peso/Alto/Ancho/Profundidad (si están cargados), Variantes (vacías), Categoría jerárquica.
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
 - Descripción enriquecida: se muestra en una card dedicada y puede editarse por Admin/Colab (persistencia vía `PATCH /products/{id}` con `description_html`). Toda la UI (incluyendo admins) ve una vista previa HTML sanitizada: se eliminan `script`, `iframe`, `object`, `embed` y atributos `on*` antes de inyectar el contenido, y si el resultado queda vacío se muestra el fallback "Sin descripción".
- Visibilidad invitados: el detalle `/productos/:id` admite accesos con rol `guest` en modo sólo lectura. Los invitados pueden ver nombre/canónico, precio efectivo y la vista previa de descripción enriquecida, pero no se muestran controles de edición ni acciones IA.
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
