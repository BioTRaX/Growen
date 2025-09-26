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

## Alta/Edición de Producto Canónico
- Campos: `name`, `brand`, `sku_custom` (opcional), `category_id`, `subcategory_id`.
- Botón "Auto" de SKU:
  - Consulta `GET /catalog/next-seq?category_id=...` para proponer un SKU de forma `XXX_####_YYY`.
  - La UI muestra una vista previa; la generación y validación final se hacen en backend.
- Selección de categoría/subcategoría:
  - Subcategoría se filtra por la categoría elegida.
  - Botones "Nueva" abren modales para crear categorías en línea (padre nulo) o subcategorías (con padre).

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
