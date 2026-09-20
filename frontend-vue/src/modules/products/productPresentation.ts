// NG-HEADER: Nombre de archivo: productPresentation.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/productPresentation.ts
// NG-HEADER: Descripción: Reglas de presentación puras del catálogo Vue de Productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import type { ProductListItem } from './types'

export function effectiveSalePrice(item: ProductListItem): number | null {
  return item.canonical_sale_price ?? item.precio_venta
}
