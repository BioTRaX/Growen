// NG-HEADER: Nombre de archivo: Stock.spec.tsx
// NG-HEADER: Ubicación: frontend/src/pages/Stock.spec.tsx
// NG-HEADER: Descripción: Pruebas del enriquecimiento canónico masivo desde Stock.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Stock from './Stock'

const { listCategories, post, push, searchProducts } = vi.hoisted(() => ({
  listCategories: vi.fn(),
  post: vi.fn(),
  push: vi.fn(),
  searchProducts: vi.fn(),
}))

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ state: { role: 'admin', isAuthenticated: true } }),
}))
vi.mock('../components/ToastProvider', () => ({ useToast: () => ({ push }) }))
vi.mock('../components/supplier/SupplierAutocomplete', () => ({ default: () => null }))
vi.mock('../components/CatalogHistoryModal', () => ({ default: () => null }))
vi.mock('../services/http', () => ({ default: { post }, baseURL: '/api' }))
vi.mock('../services/categories', () => ({ listCategories }))
vi.mock('../services/catalogs', () => ({ generateCatalog: vi.fn(), headLatestCatalog: vi.fn() }))
vi.mock('../services/productsEx', () => ({
  updateSalePrice: vi.fn(),
  updateSupplierBuyPrice: vi.fn(),
  updateSupplierSalePrice: vi.fn(),
}))
vi.mock('../services/products', () => ({
  deleteProducts: vi.fn(),
  searchProducts,
  updateStock: vi.fn(),
}))

const products = [
  { product_id: 11, canonical_product_id: 101, name: 'Producto A', stock: 5, supplier: { id: 1, name: 'Proveedor' } },
  { product_id: 12, canonical_product_id: 102, name: 'Producto B', stock: 4, supplier: { id: 1, name: 'Proveedor' } },
]

describe('Stock enrichment', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    listCategories.mockResolvedValue([])
    searchProducts.mockResolvedValue({ items: products, total: products.length })
  })

  it('conserva seleccionados sólo los productos que el batch no pudo despachar', async () => {
    post.mockResolvedValueOnce({
      data: {
        batch_id: 'batch-partial',
        jobs: [
          { product_id: 11, canonical_product_id: 101, job_id: 'job-11', status: 'queued', error: null },
          { product_id: 12, canonical_product_id: 102, job_id: 'job-12', status: 'pending', error: 'Enrich deshabilitado' },
        ],
        skipped: [],
      },
    })
    render(<MemoryRouter><Stock /></MemoryRouter>)
    await screen.findByText('Producto A')
    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[0])
    fireEvent.click(checkboxes[1])

    fireEvent.click(screen.getByRole('button', { name: 'Enriquecer 2 producto(s) con IA' }))

    await waitFor(() => {
      expect(push).toHaveBeenCalledWith({
        kind: 'info',
        message: 'Enriquecimiento parcial: 1 enviado, 1 no procesado',
      })
    })
    await waitFor(() => {
      const current = screen.getAllByRole('checkbox') as HTMLInputElement[]
      expect(current[0].checked).toBe(false)
      expect(current[1].checked).toBe(true)
    })
  })

  it('envía un representante y acepta todo el grupo cuando comparten canónico', async () => {
    searchProducts.mockResolvedValue({
      items: [
        { ...products[0], canonical_product_id: 101 },
        { ...products[1], canonical_product_id: 101 },
      ],
      total: 2,
    })
    post.mockResolvedValueOnce({
      data: {
        batch_id: 'batch-deduplicated',
        jobs: [{ product_id: 11, canonical_product_id: 101, job_id: 'job-11', status: 'queued', error: null }],
        skipped: [],
      },
    })
    render(<MemoryRouter><Stock /></MemoryRouter>)
    await screen.findByText('Producto A')
    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[0])
    fireEvent.click(checkboxes[1])

    fireEvent.click(screen.getByRole('button', { name: 'Enriquecer 2 producto(s) con IA' }))

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/canonical-products/enrichment-batches', {
        client_request_id: expect.any(String),
        product_ids: [11],
        scope: 'full',
      })
    })
    expect(push).toHaveBeenCalledWith({ kind: 'success', message: 'Productos enviados a enriquecimiento' })
    expect(screen.queryByRole('button', { name: /Enriquecer .* producto/ })).not.toBeInTheDocument()
  })
})
