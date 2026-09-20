// NG-HEADER: Nombre de archivo: useStockList.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/stock/composables/useStockList.spec.ts
// NG-HEADER: Descripción: Pruebas de URL, debounce y reemplazo del listado Stock.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { listStock } from '../api/stock'
import { useStockList } from './useStockList'

vi.mock('../api/stock', () => ({ listStock: vi.fn() }))
const Host = defineComponent({ setup: () => useStockList(), template: '<div />' })

async function mountAt(path: string) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/stock', component: Host }] })
  await router.push(path)
  await router.isReady()
  return { router, wrapper: mount(Host, { global: { plugins: [router] } }) }
}

describe('useStockList', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.mocked(listStock).mockResolvedValue({ page: 1, page_size: 50, total: 0, items: [] }) })
  afterEach(() => { vi.useRealTimers(); vi.clearAllMocks() })

  it('restaura filtros desde URL y espera 300 ms', async () => {
    await mountAt('/stock?q=neem&supplier_id=3&stock=eq:0&page=2')
    expect(listStock).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()
    expect(listStock).toHaveBeenCalledWith(expect.objectContaining({ q: 'neem', supplier_id: 3, stock: 'eq:0', page: 2 }), expect.any(AbortSignal))
  })

  it('reemplaza la URL y reinicia página al cambiar de pestaña', async () => {
    const { router, wrapper } = await mountAt('/stock?q=neem&page=3')
    await (wrapper.vm as unknown as { setFilters: (patch: object) => Promise<void> }).setFilters({ stock: 'eq:0' })
    expect(router.currentRoute.value.query).toEqual({ q: 'neem', stock: 'eq:0' })
  })
})
