// NG-HEADER: Nombre de archivo: products.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/api/products.spec.ts
// NG-HEADER: Descripción: Pruebas del mapeo entre filtros Vue y contrato HTTP de Productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { describe, expect, it } from 'vitest'
import { DEFAULT_PRODUCT_FILTERS } from '../productFilters'
import { toProductApiParams } from './products'

describe('toProductApiParams', () => {
  it('mapea recent al nombre esperado por FastAPI', () => {
    expect(toProductApiParams({ ...DEFAULT_PRODUCT_FILTERS, q: '  neem ', recent: 30, stock: 'eq:0' })).toEqual({
      page: 1,
      page_size: 50,
      type: 'all',
      q: 'neem',
      stock: 'eq:0',
      created_since_days: 30,
    })
  })

  it('omite filtros opcionales vacíos', () => {
    expect(toProductApiParams(DEFAULT_PRODUCT_FILTERS)).toEqual({ page: 1, page_size: 50, type: 'all' })
  })
})
