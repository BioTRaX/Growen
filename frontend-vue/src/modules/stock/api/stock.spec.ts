// NG-HEADER: Nombre de archivo: stock.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/stock/api/stock.spec.ts
// NG-HEADER: Descripción: Pruebas de contratos HTTP, filtros y descargas de Stock Vue.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { beforeEach, describe, expect, it, vi } from 'vitest'

const http = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
const listProducts = vi.hoisted(() => vi.fn())
vi.mock('../../../services/http', () => ({ http }))
vi.mock('../../products/api/products', () => ({ listProducts }))

import { createShortage, downloadStockExport, listShortages, listStock, openStockPdf } from './stock'

const filters = { q: ' neem ', supplier_id: 3, category_id: 8, stock: 'gt:0' as const, page: 2, page_size: 25 }

describe('cliente HTTP de Stock', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('URL', { createObjectURL: vi.fn(() => 'blob:test'), revokeObjectURL: vi.fn() })
  })

  it('reutiliza el listado de Productos sin acumular páginas', async () => {
    listProducts.mockResolvedValue({ page: 2, page_size: 25, total: 0, items: [] })
    await listStock(filters, new AbortController().signal)
    expect(listProducts).toHaveBeenCalledWith(expect.objectContaining({ page: 2, page_size: 25, type: 'all' }), expect.any(AbortSignal))
  })

  it.each(['xlsx', 'csv'] as const)('descarga %s con el mismo conjunto de filtros', async (format) => {
    http.get.mockResolvedValue({ data: new Blob(['stock']) })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await downloadStockExport(format, filters)
    expect(http.get).toHaveBeenCalledWith(`/stock/export.${format}`, expect.objectContaining({
      responseType: 'blob',
      params: expect.objectContaining({ q: 'neem', supplier_id: 3, category_id: 8, stock: 'gt:0', type: 'all' }),
    }))
    expect(click).toHaveBeenCalled()
  })

  it('abre el PDF desde un blob y registra faltantes decimales', async () => {
    http.get.mockResolvedValue({ data: new Blob(['pdf']) })
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    await openStockPdf(filters)
    expect(open).toHaveBeenCalledWith('blob:test', '_blank', 'noopener,noreferrer')
    http.post.mockResolvedValue({ data: { id: 1, new_stock: 8.75 } })
    await createShortage({ product_id: 4, quantity: 1.25, reason: 'GIFT' })
    expect(http.post).toHaveBeenCalledWith('/stock/shortages', { product_id: 4, quantity: 1.25, reason: 'GIFT' })
  })

  it('propaga motivo y paginación al listado de faltantes', async () => {
    http.get.mockResolvedValue({ data: { items: [], total: 0, page: 2, pages: 0 } })
    await listShortages({ page: 2, page_size: 20, reason: 'UNKNOWN' })
    expect(http.get).toHaveBeenCalledWith('/stock/shortages', { params: { page: 2, page_size: 20, reason: 'UNKNOWN' }, signal: undefined })
  })
})
