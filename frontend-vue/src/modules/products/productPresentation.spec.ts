// NG-HEADER: Nombre de archivo: productPresentation.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/productPresentation.spec.ts
// NG-HEADER: Descripción: Pruebas de precedencia visual de precios de Productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { describe, expect, it } from 'vitest'
import { effectiveSalePrice } from './productPresentation'
import type { ProductListItem } from './types'

const product: ProductListItem = {
  product_id: 1,
  name: 'Producto',
  preferred_name: 'Producto',
  supplier: { id: 2, slug: 'proveedor', name: 'Proveedor' },
  supplier_item_id: 3,
  precio_compra: 100,
  precio_venta: 200,
  canonical_sale_price: 250,
  compra_minima: null,
  category_id: null,
  subcategory_id: null,
  category_path: null,
  stock: 5,
  updated_at: null,
  canonical_product_id: 4,
  canonical_sku: 'ABC_0001_DEF',
  canonical_name: 'Producto',
  first_variant_sku: null,
  tags: [],
  image_url: null,
  images_count: 0,
  primary_image_id: null,
}

describe('effectiveSalePrice', () => {
  it('prioriza el precio canónico', () => {
    expect(effectiveSalePrice(product)).toBe(250)
  })

  it('usa el precio del proveedor como fallback', () => {
    expect(effectiveSalePrice({ ...product, canonical_sale_price: null })).toBe(200)
  })
})
