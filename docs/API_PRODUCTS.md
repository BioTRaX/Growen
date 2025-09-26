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
- `name` y `precio_venta` retornan ya con fallback: si el item tiene canónico, se prioriza el nombre y precio del canónico; si no, se usan los del proveedor.
- Campos auxiliares: `canonical_product_id`, `canonical_sale_price`, `supplier_title`, `canonical_name`.
- Nuevos campos: `canonical_sku` (si hay canónico) y `first_variant_sku` (primer SKU de variante interna, como fallback). La UI muestra debajo del nombre el SKU preferido: primero `canonical_sku`, si no existe `first_variant_sku`.

Ejemplo:
`GET /products?type=canonical&stock=gt:0&page=1&page_size=50`

---

## GET /products/{id}
Detalle de un producto interno. Además de los campos básicos (`id`, `title`, `slug`, `stock`, `sku_root`, `description_html`, `category_path`, `images`), ahora incluye campos canónicos cuando existe una equivalencia:

- `canonical_product_id`: id del canónico vinculado (o null)
- `canonical_sale_price`: precio de venta del canónico (si existe)
- `canonical_sku`: SKU canónico propio (formato XXX_####_YYY), si existe
- `canonical_ng_sku`: SKU NG-######
- `canonical_name`: nombre del canónico

UI: en la ficha de producto se muestra el `SKU` priorizando `canonical_sku` cuando está disponible; de lo contrario, se muestra el `sku_root` interno.

---

## GET /stock/export.xlsx
Exporta un XLS con columnas: `NOMBRE DE PRODUCTO`, `PRECIO DE VENTA`, `CATEGORIA`, `SKU`.

Reglas de datos:
- Nombre y precio: si el item tiene canónico, se usa el nombre y precio del canónico. Si no, se usa la información del proveedor/interno.
- Categoría: preferir taxonomía del canónico. Si hay categoría y subcategoría, mostrar `Categoria > Subcategoria`. Si sólo hay categoría, `Categoria > Categoria`. Si no hay canónico, se usa el path del producto interno.
- SKU: preferir `canonical_sku` (si existe), sino usar el primer SKU de variante del producto interno.

Estilos aplicados:
- Encabezado con fondo oscuro y texto claro, negrita.
- Nombres (columna 1) en negrita.
- Ajuste automático aproximado de ancho para la primera columna.

---

## GET /stock/export.csv
Exporta un CSV con las mismas columnas y reglas que el XLS: `NOMBRE DE PRODUCTO`, `PRECIO DE VENTA`, `CATEGORIA`, `SKU`.

Notas:
- Misma lógica de selección (canónico primero; fallback a proveedor/interno).
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
