// NG-HEADER: Nombre de archivo: productFilters.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/productFilters.spec.ts
// NG-HEADER: Descripción: Pruebas de persistencia URL de filtros de Productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { describe, expect, it } from 'vitest'
import { DEFAULT_PRODUCT_FILTERS, parseProductFilters, serializeProductFilters } from './productFilters'

describe('filtros de Productos en URL', () => {
  it('usa valores seguros ante parámetros inválidos', () => {
    expect(parseProductFilters({ page: '-2', stock: 'bad', type: 'bad', recent: '90' })).toEqual(DEFAULT_PRODUCT_FILTERS)
  })

  it('conserva filtros y paginación válidos', () => {
    const filters = parseProductFilters({
      q: 'fertilizante', supplier_id: '4', category_id: '7', stock: 'gt:0', recent: '7', type: 'canonical', page: '3', page_size: '25',
    })
    expect(filters).toMatchObject({ q: 'fertilizante', supplier_id: 4, category_id: 7, stock: 'gt:0', recent: 7, type: 'canonical', page: 3, page_size: 25 })
    expect(serializeProductFilters(filters)).toEqual({
      q: 'fertilizante', supplier_id: '4', category_id: '7', stock: 'gt:0', recent: '7', type: 'canonical', page: '3', page_size: '25',
    })
  })

  it('omite valores por defecto de la URL', () => {
    expect(serializeProductFilters(DEFAULT_PRODUCT_FILTERS)).toEqual({})
  })
})
