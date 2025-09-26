// NG-HEADER: Nombre de archivo: ProductsDrawer.refresh.test.tsx
// NG-HEADER: Ubicación: frontend/src/__tests__/ProductsDrawer.refresh.test.tsx
// NG-HEADER: Descripción: Test para verificar refetch tras creación de canónico en ProductsDrawer.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { describe, it, expect, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import React from 'react'

// Mock de servicios
vi.mock('../services/products', async () => {
  const actual = await vi.importActual<any>('../services/products')
  return {
    ...actual,
    searchProducts: vi.fn().mockResolvedValue({ items: [{ product_id: 1, name: 'P1' }], total: 1 })
  }
})

vi.mock('../services/categories', async () => {
  const actual = await vi.importActual<any>('../services/categories')
  return {
    ...actual,
    listCategories: vi.fn().mockResolvedValue([])
  }
})

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ state: { role: 'admin' } })
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<any>('react-router-dom')
  return { ...actual, Link: ({ children }: any) => <a>{children}</a> }
})

// Mock del modal de creación: cuando se renderiza, dispara onCreated inmediatamente
vi.mock('../components/ProductCreateModal', () => ({
  __esModule: true,
  default: ({ onCreated, onClose }: any) => {
    React.useEffect(() => {
      onCreated?.()
      // cerrar para limpiar
      onClose?.()
    }, [])
    return <div data-testid="mock-create-modal">Modal</div>
  }
}))

import ProductsDrawer from '../components/ProductsDrawer'
import * as productsSvc from '../services/products'

function advanceTimers(ms: number) {
  act(() => { vi.advanceTimersByTime(ms) })
}

describe('ProductsDrawer refresh after canonical creation', () => {
  it('forces refetch on page 1 after onCreated', async () => {
    vi.useFakeTimers()
    const sp = productsSvc as unknown as { searchProducts: any }
    sp.searchProducts.mockResolvedValueOnce({ items: [{ product_id: 1, name: 'P1' }], total: 1 })

    render(<ProductsDrawer open={true} onClose={() => {}} mode="embedded" />)

    // Esperar llamada inicial (debounce 300ms)
    advanceTimers(300)
    expect(sp.searchProducts).toHaveBeenCalledTimes(1)
    expect(sp.searchProducts.mock.calls[0][0]).toMatchObject({ page: 1 })

    // Abrir modal "Nuevo producto"
    const btn = await screen.findByRole('button', { name: /nuevo producto/i })
    await userEvent.click(btn)

    // El mock del modal dispara onCreated y fuerza refresh
    advanceTimers(300)

    // Esperamos 2da llamada (refetch)
    expect(sp.searchProducts).toHaveBeenCalledTimes(2)
    expect(sp.searchProducts.mock.calls[1][0]).toMatchObject({ page: 1 })
  })
})
