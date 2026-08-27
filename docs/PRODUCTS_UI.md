<!-- NG-HEADER: Nombre de archivo: PRODUCTS_UI.md -->
<!-- NG-HEADER: Ubicación: docs/PRODUCTS_UI.md -->
<!-- NG-HEADER: Descripción: Documentación de la UI de Productos y creación/edición de canónicos. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# UI de Productos y Canónicos

## Centro Conocimiento (2026-07-26)

La ficha canónica muestra **Conocimiento** para staff. El centro compartido con Mercado reúne fuentes, documentos, imágenes, videos, hechos, historial e IA; permite alta, edición, procesamiento, revalidación, archivado/restauración y upload. Sus etiquetas/capacidades nunca se agregan a `Product.tags`. Mercado lo abre filtrado por `market`.

Al editar una fuente Mercado, staff configura tipo de lectura, obligatoriedad, estado y confirma explícitamente ARS con entrega en Argentina. Sin esa confirmación el activo se conserva y puede ser evidencia, pero no participa del scraping ni del promedio.

## Detalle canónico Vue y Enrich v2 (2026-07-25)

`/productos/:id` está activo en Vue. El ID sigue identificando el registro interno, pero nombre preferido, descripción, medidas, especificaciones, instrucciones y revisión provienen del canónico vinculado. Todos los internos equivalentes comparten contenido; stock, tags e imágenes se agregan y el inventario inferior lista cada `Product.id` una sola vez con sus ofertas.

El SKU canónico muestra un lápiz para `colaborador|admin`. La edición requiere confirmar con el botón de check o Enter; Escape/cancelar descarta el borrador y perder foco nunca guarda. El backend normaliza a mayúsculas, exige `XXX_0000_YYY` y valida unicidad antes del commit. Un SKU existente devuelve `409 duplicate_sku`, mantiene abierto el editor y no aplica ningún cambio.

Sin canónico se muestra una ficha básica y la acción para asignarlo; Enrich queda bloqueado. El stock es sólo lectura y enlaza a `/stock`. Staff ve actividad, fuentes, selección de campos y una card que consume exclusivamente `/market`. La ruta `/productos/:id/imagen` y equivalencias avanzadas continúan en React.

Los jobs pueden quedar `review_required` o `partially_applied`; la aplicación exige `expected_content_revision` y devuelve `409` ante cambios concurrentes. El backend entrega HTML escapado/permitido: el modelo sólo devuelve texto y datos estructurados.

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
- Stock: rutas `/stock` y `/stock/shortages` activas en Vue; contrato operativo en `docs/STOCK.md`.
- Imágenes: ruta `/imagenes-productos` activa en Vue y visible sólo para `colaborador` y `admin`.

El listado admite `cliente`, `proveedor`, `colaborador` y `admin`. El detalle `/productos/:id` admite también `guest`; el historial confirmado de compras, remitos y movimientos de stock se muestra únicamente a staff.

Las capacidades pendientes deben consultarse en el manifiesto y en `docs/FRONTEND_MIGRATION_VUE.md`. Este documento no mantiene un segundo estado de migración. Enriquecimiento masivo, completar precios y catálogos están disponibles en Vue.

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

### Relación con Stock

Stock reutiliza el precio efectivo canónico → proveedor y los contratos de producto, pero mantiene su documentación funcional y de exportaciones en `docs/STOCK.md`. Esta separación evita duplicar reglas entre Productos y Stock.

## Detalle de Producto
- La ruta activa `/productos/:id` usa Vue y conserva el `Product.id` únicamente como entrada compatible. Si existe vínculo, identidad, descripción y datos técnicos se resuelven desde `CanonicalProduct`.
- Productos internos equivalentes muestran el mismo contenido canónico. La ficha agrega stock, tags, imágenes, historial y ofertas sin duplicar registros, y lista al final el inventario interno vinculado.
- El stock agregado es de sólo lectura; los ajustes operativos continúan en `/stock`.
- Un producto sin canónico muestra el estado `canonical_required`, conserva sus datos internos básicos y no permite iniciar enriquecimiento hasta crear o asignar el canónico.
- “Generar contenido” crea un job mediante `POST /canonical-products/{id}/enrichment-jobs`. La vista hace polling cancelable, presenta fuentes, propuesta, confianza y campos autoaplicados o pendientes.
- Al reabrir la ficha, Vue recupera el último job y su panel **Diagnóstico de proveedores**. Para cada intento muestra código seguro, HTTP, request ID y límites/resets disponibles, sin exponer prompts ni respuestas remotas.
- La aplicación manual usa `expected_content_revision`; un cambio concurrente responde `409` y nunca sobrescribe silenciosamente contenido más reciente.
- El backend renderiza y sanitiza el HTML permitido. El proveedor IA sólo devuelve texto y datos estructurados.
- Las descripciones se redactan como contenido publicable: voz activa, 2 a 4 oraciones breves y tono natural, sin mencionar fuentes, investigación o evidencia dentro del texto comercial.
- Especificaciones e instrucciones se muestran como campos y listas con etiquetas legibles, no como JSON crudo. La procedencia permanece en la trazabilidad del job y no se mezcla con los valores del producto.
- El botón **Conocimiento** abre la vista dedicada `/productos/:id/Conocimiento`, disponible para `colaborador` y `admin`. La página reutiliza el centro canónico completo sin overlay: fuentes, documentos, imágenes, videos, hechos, historial y jobs IA conservan sus operaciones y formularios.
- Enrich v2 investiga descripción y especificaciones. No calcula, muestra ni edita valores monetarios: la card Mercado consume exclusivamente `/market`.
- La trazabilidad y el historial se consultan en los endpoints de jobs y versiones canónicas. Ya no se usa un archivo `.txt` asociado al producto como fuente primaria.
- Invitados y clientes acceden a la ficha en modo lectura; colaborador y admin pueden operar el enriquecimiento según sus permisos.
- Imágenes avanzadas permanecen temporalmente en `/productos/:id/imagen` React y las equivalencias avanzadas siguen en la administración legacy para conservar rollback granular.

## Acciones masivas
- El batch de Enrich v2 crea un grupo idempotente de jobs para canónicos únicos, omite productos internos sin canónico y reporta resultados parciales.
- Los endpoints `/products/enrich-multiple` y `/products/{id}/enrich` se conservan sólo como adaptadores de compatibilidad para el fallback React; no calculan precios de mercado.
- Productos Vue también permite completar precios faltantes por proveedor, generar un catálogo desde la selección y consultar, ver, descargar o eliminar (admin) el histórico.

## Flags y comportamiento IA
- `ENRICH_V2_ENABLED` habilita los contratos y el worker de Enrich v2.
- `ENRICH_WEB_REQUIRED=1` exige investigación mediante MCP Web Search. MCP Products no participa del pipeline.
- `ENRICH_AI_MODE=auto` intenta OpenAI y sólo usa Ollama si está configurado y su salida valida el mismo esquema. Los modos explícitos no cambian de proveedor silenciosamente.
- No existe fallback de eco. Sin proveedor válido el job termina `failed` con un error explícito y no aplica campos.
- La configuración completa, el despliegue y el smoke vigente están documentados en `docs/ENRICH_V2_DEPLOYMENT_SMOKE_20260725.md`.

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
