<!-- NG-HEADER: Nombre de archivo: CATEGORIES.md -->
<!-- NG-HEADER: Ubicación: docs/CATEGORIES.md -->
<!-- NG-HEADER: Descripción: Guía de categorías (creación manual, niveles, asociación a productos) -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Categorías: creación y uso

Este documento describe cómo crear categorías manualmente (2 niveles: Categoria y SubCategoria), cómo se almacenan y cómo asociarlas a productos.

## Modelo

- Tabla `categories` con jerarquía simple por `parent_id`.
- Nivel 1: `Categoria` (`parent_id = null`).
- Nivel 2: `SubCategoria` (`parent_id = id de la Categoria`). En el formulario de canónicos, la "Subcategoría" puede seleccionarse de manera independiente como una categoría secundaria; el campo "padre" es opcional al crear una nueva subcategoría desde la UI.
- Los productos (`products.category_id`) referencian la categoría final (nivel 2 o nivel 1 si no hay subcategoría).

## Endpoints existentes

- Listar categorías
  - GET /categories
  - Roles: cliente, proveedor, colaborador, admin
  - Respuesta: `[{ id, name, parent_id, path }]` con `path` tipo `Categoria>SubCategoria`.

- Crear categoría
  - POST /categories
  - Roles: colaborador, admin (requiere CSRF)
  - Body: `{ "name": "Sustratos", "parent_id": null }` para Categoria; `{ "name": "Premium", "parent_id": 1 }` para SubCategoria.
  - Reglas: unicidad por (name, parent_id); valida `parent_id` existente.

## Próximos endpoints (plan)

- Actualizar producto (categoría)
  - PATCH /products/{product_id}
  - Body: `{ "category_id": 123 }`
  - Reglas: `category_id` debe existir; registrar en `AuditLog` (action: `product_update.category`).

- Exportación XLS de Stock
  - GET /stock/export.xlsx
  - Roles: colaborador, admin
  - Parámetros: mismos filtros que `GET /products` (`q`, `supplier_id`, `category_id`, `stock`, `page_size` ignorado; exporta todo el match razonable con límite seguro p.ej. 10k filas).
  - Columnas: `PRODUCTO`, `PRECIO_VENTA`, `CATEGORIA`, `SKU_PROPIO`.

## Flujo UI (plan)

- En `/productos` agregar botones:
  - "Nueva categoría": modal con input `name` crea nivel 1.
  - "Nueva subcategoría": modal con selector `Categoria` padre + `name` crea nivel 2.
  - Los listados se refrescan al crear.

- En ficha `/productos/:id` agregar selector de `Categoria/SubCategoria` con guardado (PATCH producto).

- En `/stock` agregar botón oscuro "Descargar XLS" que descarga el archivo respetando filtros vigentes.

## Consideraciones

- i18n: nombres libres (permitir acentos y espacios). Evitar duplicados por nivel.
- Auditoría: registrar siempre cambios de categoría del producto.
- Permisos: creación limitada a `colaborador|admin`; lectura abierta a todos los roles internos.
- Rendimiento: cachear listado de categorías en frontend; invalidar tras crear.
