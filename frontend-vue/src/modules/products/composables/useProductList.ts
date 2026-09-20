// NG-HEADER: Nombre de archivo: useProductList.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/composables/useProductList.ts
// NG-HEADER: Descripción: Estado remoto, URL y cancelación del listado Vue de Productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getHttpErrorMessage } from '../../../services/http'
import { listProducts } from '../api/products'
import { parseProductFilters, serializeProductFilters } from '../productFilters'
import type { ProductListFilters, ProductListItem } from '../types'

export function useProductList(debounceMs = 300) {
  const route = useRoute()
  const router = useRouter()
  const items = ref<ProductListItem[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref('')
  const filters = computed(() => parseProductFilters(route.query))
  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / filters.value.page_size)))
  let timer: ReturnType<typeof setTimeout> | undefined
  let controller: AbortController | undefined
  let requestSequence = 0

  async function load(): Promise<void> {
    controller?.abort()
    controller = new AbortController()
    const sequence = ++requestSequence
    loading.value = true
    error.value = ''
    try {
      const response = await listProducts(filters.value, controller.signal)
      if (sequence !== requestSequence) return
      items.value = response.items
      total.value = response.total
      if (response.total > 0 && filters.value.page > Math.ceil(response.total / response.page_size)) {
        await setFilters({ page: 1 }, false)
      }
    } catch (cause) {
      if (sequence !== requestSequence) return
      const message = getHttpErrorMessage(cause, 'No se pudo cargar el catálogo de productos')
      if (message) {
        error.value = message
        items.value = []
        total.value = 0
      }
    } finally {
      if (sequence === requestSequence) loading.value = false
    }
  }

  function scheduleLoad(): void {
    controller?.abort()
    window.clearTimeout(timer)
    timer = window.setTimeout(load, debounceMs)
  }

  async function setFilters(patch: Partial<ProductListFilters>, resetPage = true): Promise<void> {
    const next = { ...filters.value, ...patch }
    if (resetPage && !Object.prototype.hasOwnProperty.call(patch, 'page')) next.page = 1
    await router.replace({ query: serializeProductFilters(next) })
  }

  function retry(): void {
    window.clearTimeout(timer)
    void load()
  }

  watch(filters, scheduleLoad, { immediate: true })
  onBeforeUnmount(() => {
    window.clearTimeout(timer)
    controller?.abort()
  })

  return { items, total, loading, error, filters, totalPages, setFilters, retry }
}
