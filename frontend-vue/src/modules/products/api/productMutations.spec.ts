// NG-HEADER: Nombre de archivo: productMutations.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/api/productMutations.spec.ts
// NG-HEADER: Descripción: Pruebas de contratos HTTP para mutaciones de Productos Vue.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { beforeEach, describe, expect, it, vi } from 'vitest'

const http = vi.hoisted(() => ({
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
  get: vi.fn(),
}))

vi.mock('../../../services/http', () => ({ http }))

import { createProductCategory, deleteProducts, updateCanonicalSalePrice, updateProductStock, updateSupplierSalePrice } from './products'

describe('mutaciones HTTP de Productos', () => {
  beforeEach(() => vi.clearAllMocks())

  it('actualiza stock mediante el producto interno', async () => {
    http.patch.mockResolvedValue({ data: { product_id: 7, stock: 12 } })
    await expect(updateProductStock(7, 12)).resolves.toEqual({ product_id: 7, stock: 12 })
    expect(http.patch).toHaveBeenCalledWith('/products/7/stock', { stock: 12 })
  })

  it('envía el saldo leído para detectar escrituras concurrentes', async () => {
    http.patch.mockResolvedValue({ data: { product_id: 7, stock: 10.25 } })
    await updateProductStock(7, 10.25, 12.5)
    expect(http.patch).toHaveBeenCalledWith('/products/7/stock', { stock: 10.25, expected_stock: 12.5 })
  })

  it('separa precio canónico y precio de proveedor', async () => {
    http.patch.mockResolvedValue({ data: { id: 4, sale_price: 250 } })
    await updateCanonicalSalePrice(4, 250)
    expect(http.patch).toHaveBeenLastCalledWith('/products-ex/products/4/sale-price', { sale_price: 250 })
    await updateSupplierSalePrice(9, 180)
    expect(http.patch).toHaveBeenLastCalledWith('/products-ex/supplier-items/9/sale-price', { sale_price: 180 })
  })

  it('usa el endpoint de borrado protegido y envía ids en el body DELETE', async () => {
    http.delete.mockResolvedValue({ data: { requested: [1, 2], deleted: [1], blocked_stock: [2], blocked_refs: [] } })
    await deleteProducts([1, 2])
    expect(http.delete).toHaveBeenCalledWith('/catalog/products', { data: { ids: [1, 2] } })
  })

  it('crea categorías y subcategorías por tipo plano', async () => {
    http.post.mockResolvedValue({ data: { id: 12, name: 'Sustratos', kind: 'subcategory', parent_id: null, path: 'Sustratos' } })
    await expect(createProductCategory('  Sustratos  ', 'subcategory')).resolves.toMatchObject({ id: 12, kind: 'subcategory' })
    expect(http.post).toHaveBeenCalledWith('/categories', { name: 'Sustratos', kind: 'subcategory' })
  })
})
