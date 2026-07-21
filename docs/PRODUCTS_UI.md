<!-- NG-HEADER: Nombre de archivo: PRODUCTS_UI.md -->
<!-- NG-HEADER: Ubicación: docs/PRODUCTS_UI.md -->
<!-- NG-HEADER: Descripción: Documentación de la UI de Productos y creación/edición de canónicos. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# UI de Productos y Canónicos

## Taxonomía plana y tags (2026-07-18)

Categoría y subcategoría son dos listas independientes identificadas por `kind=category|subcategory`. Sus autocompletes usan un valor numérico estable y `v-model:search`: aceptan escritura real y muestran **Agregar “…”** cuando no existe una coincidencia normalizada dentro del mismo tipo. El mismo nombre puede existir una vez en cada tipo; `parent_id` ya no filtra la selección.

En el alta individual ambas clasificaciones y los tags son opcionales. En un canónico, categoría y subcategoría son obligatorias porque generan el SKU y la exportación `Categoría > Subcategoría`. El wizard permite tags comunes en Preparar y particulares en Completar; el batch recibe la unión normalizada. El borrador vigente usa `growen.products.mass-canonical.v3:<userId>` y migra v2 agregando listas vacías.

Staff puede editar todos los tags desde el detalle y agregarlos de forma aditiva a una selección en `/productos`. React permanece como fallback hasta completar el smoke de paridad.

## Alta masiva canónica Vue (2026-07-17)

Los roles `colaborador` y `admin` pueden seleccionar hasta 100 filas pendientes en `/productos` y abrir **Crear canónicos**. Se omiten, con aviso, filas ya canonizadas, sin oferta de proveedor o duplicadas.

El wizard recorre Preparar, Completar, Revisar y Procesar. Nombre, categoría y subcategoría tipadas son obligatorios; marca y tags son opcionales. Ambos selectores son independientes. La UI obtiene un SKU provisional desde `POST /canonical-products/sku-preview`, pero no lo reenvía como definitivo. El worker asigna el SKU transaccional, crea el canónico, la equivalencia y los tags como una unidad y expone progreso mediante `GET /canonical-products/batch-jobs/{job_id}`.

Los borradores usan `growen.products.mass-canonical.v3:<userId>`, vencen a los 30 días y conservan un job activo. La primera carga migra v2 o convierte una sesión React válida desde `mass_cannon_session`. Los lotes parciales muestran el error por fila y permiten corregir y reenviar únicamente los fallidos.

Si el primer despacho falla antes de procesar ítems —por ejemplo, porque Redis no está disponible—, el wizard muestra **Reintentar lote** y repite la solicitud con el mismo identificador idempotente. El backend reencola el lote `FAILED` existente en lugar de devolverlo sin trabajo o crear un duplicado.

En desarrollo, iniciar Growen con `.\scripts\start-dev.ps1 -WithCatalogWorker` antes de usar este wizard. El launcher comprueba Redis y el consumidor Dramatiq; la creación individual mediante `POST /canonical-products` sigue siendo síncrona y no requiere esos servicios.

## Catálogo operativo y mutaciones Vue (2026-07-17)

La ruta `/productos` dispone de búsqueda con debounce, filtros de proveedor, categoría, stock, recientes y tipo, además de paginación configurable. Los filtros se guardan como parámetros de URL y se restauran al regresar desde el detalle.

La tabla muestra nombre preferido, SKU, proveedor, precio efectivo, stock, categoría y estado canónico. El precio efectivo respeta la regla del backend: precio canónico y, si falta, precio del proveedor.

Para `colaborador` y `admin` se recuperaron las operaciones principales:

- Alta de producto interno y oferta de proveedor con stock inicial, precios, categoría, subcategoría y tags opcionales. Ambas taxonomías son buscables y creables por tipo. Si el producto interno se crea pero falla el vínculo, el diálogo conserva el contexto y permite corregir proveedor o SKU y reintentar.
- Edición de stock con hasta dos decimales entre 0 y 1.000.000.000; Vue envía el saldo leído como `expected_stock` y muestra el conflicto 409 sin sobrescribir.
- Edición del precio de venta efectivo: actualiza el canónico cuando existe y la oferta del proveedor como fallback.
- Selección por fila, borrado individual y masivo con confirmación. El backend bloquea productos con stock o referencias de compras y devuelve un resumen parcial.

La barra lateral agrupa bajo **Productos**:

- Catálogo: operativo en Vue.
- Stock: vistas `/stock` y `/stock/shortages` implementadas para validación en Vue; el manifiesto conserva `legacy/pending` hasta activar Productos/Catálogos y completar el smoke por rol.
- Imágenes: ruta `/imagenes-productos` visible sólo para `colaborador` y `admin`, pendiente de migración.

El listado admite `cliente`, `proveedor`, `colaborador` y `admin`. El detalle `/productos/:id` admite también `guest`; el historial confirmado de compras, remitos y movimientos de stock se muestra únicamente a staff.

Esta vista no sustituye todavía la administración avanzada React de imágenes, detalle enriquecido, mercado, equivalencias y preferencias de columnas. Enriquecimiento masivo, completar precios y catálogos ya están disponibles en Vue.

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
  - El PDF se abre desde un blob en una nueva pestaña y revoca su URL temporal; el backend usa ReportLab incluido en el proyecto, sin dependencia nueva.
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
- En Productos Vue (`/productos`), al seleccionar múltiples productos aparece el botón “Enriquecer”. Stock Vue no incorpora selección ni operaciones avanzadas.
  - Llama `POST /products/enrich-multiple` con `{ ids: [...], force?: boolean }` (límite de 20 IDs por solicitud).
  - La UI limpia la selección y refresca el listado al finalizar.
- Productos Vue también permite completar precios faltantes por proveedor, generar un catálogo desde la selección y consultar, ver, descargar o eliminar (admin) el histórico.

## Flags y comportamiento IA
- El enriquecimiento IA puede adjuntar resultados de búsqueda web (MCP) al prompt cuando:
  - `AI_USE_WEB_SEARCH=1` y `ai_allow_external=true` (ver configuración), y
  - Existe rol con permisos (admin/colaborador).
- Auditoría: se registran `web_search_query` y `web_search_hits` cuando la búsqueda web está activa.

## Alta/Edición de Producto Canónico

> Esta sección describe el formulario React heredado. El wizard Vue vigente se documenta al inicio de este archivo.

- Campos: `name`, `brand`, `sku_custom` (opcional), `category_id`, `subcategory_id`.
- Botón "Auto" de SKU:
  - Consulta `GET /catalog/next-seq?category_id=...` para proponer un SKU de forma `XXX_####_YYY`.
  - Es una vista previa no reservante; la generación y validación final se hacen en backend.
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
