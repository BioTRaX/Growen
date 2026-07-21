// NG-HEADER: Nombre de archivo: useProductList.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/composables/useProductList.spec.ts
// NG-HEADER: Descripción: Pruebas de debounce, URL y carga del listado de Productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { listProducts } from '../api/products'
import { useProductList } from './useProductList'

vi.mock('../api/products', () => ({ listProducts: vi.fn() }))

const Host = defineComponent({
  setup() {
    return useProductList()
  },
  template: '<div />',
})

async function mountAt(path: string) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/productos', component: Host }] })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(Host, { global: { plugins: [router] } })
  return { router, wrapper }
}

describe('useProductList', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.mocked(listProducts).mockResolvedValue({ page: 1, page_size: 50, total: 0, items: [] })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('hidrata filtros desde la URL y difiere la consulta', async () => {
    await mountAt('/productos?q=neem&stock=gt:0&page=2')
    expect(listProducts).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()
    expect(listProducts).toHaveBeenCalledWith(expect.objectContaining({ q: 'neem', stock: 'gt:0', page: 2 }), expect.any(AbortSignal))
  })

  it('reinicia la página al cambiar un filtro', async () => {
    const { router, wrapper } = await mountAt('/productos?q=neem&page=3')
    await (wrapper.vm as unknown as { setFilters: (value: object) => Promise<void> }).setFilters({ stock: 'eq:0' })
    expect(router.currentRoute.value.query).toEqual({ q: 'neem', stock: 'eq:0' })
  })
})
