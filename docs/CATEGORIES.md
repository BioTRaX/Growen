<!-- NG-HEADER: Nombre de archivo: CATEGORIES.md -->
<!-- NG-HEADER: Ubicación: docs/CATEGORIES.md -->
<!-- NG-HEADER: Descripción: Guía de categorías y subcategorías planas de productos. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Categorías y subcategorías

## Modelo vigente

`categories.kind` diferencia `category` y `subcategory`. Son dos clasificaciones planas e independientes: el mismo nombre puede existir una vez en cada tipo y la unicidad se evalúa con `lower(name)`. `parent_id` se conserva únicamente para compatibilidad con datos y clientes legacy; no restringe las nuevas selecciones.

Los productos internos guardan `category_id` y `subcategory_id`, ambos opcionales. Los canónicos requieren ambos IDs con el tipo correcto porque alimentan el SKU y la exportación `Categoría > Subcategoría`. Los tags son otra dimensión, múltiple y opcional; no reemplazan la taxonomía.

## Endpoints

- `GET /categories?kind=category|subcategory`: lista plana filtrable.
- `GET /categories/search?q=...&kind=...`: búsqueda parcial por nombre y tipo.
- `POST /categories`: recibe `{ "name": "Sustratos", "kind": "subcategory" }`; requiere `colaborador|admin` y CSRF.
- `parent_id` todavía puede enviarse. Si falta `kind`, un `parent_id` presente infiere `subcategory`; esta compatibilidad es temporal.
- `POST /products` y `PATCH /products/{id}` aceptan `category_id` y `subcategory_id` independientemente.

## Flujo Vue

Los dos autocompletes usan `v-model:search`, aceptan escritura y ofrecen **Agregar “…”** cuando el nombre normalizado no existe en su tipo. El alta individual permite omitir ambos campos. El wizard canónico exige completarlos y no filtra subcategorías por padre.

## Migración y operación

Alembic head `20260718_product_taxonomy_tags_v1` migra raíces legacy a `category`, descendientes a `subcategory`, agrega `products.subcategory_id` y crea los índices normalizados. La revisión audita colisiones y aborta con diagnóstico; no fusiona datos automáticamente.

La creación está limitada a `colaborador|admin`; la lectura admite todos los roles autenticados. React permanece como fallback temporal, pero su selector jerárquico no define el contrato nuevo.
