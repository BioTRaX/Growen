// NG-HEADER: Nombre de archivo: useStockList.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/stock/composables/useStockList.ts
// NG-HEADER: Descripción: Estado remoto, filtros URL y cancelación del listado de Stock.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getHttpErrorMessage } from '../../../services/http'
import type { ProductListItem } from '../../products/types'
import { listStock } from '../api/stock'
import type { StockFilters, StockTab } from '../types'

function positive(value: unknown, fallback: number): number { const parsed = Number(value); return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback }

export function useStockList(debounceMs = 300) {
  const route = useRoute()
  const router = useRouter()
  const items = ref<ProductListItem[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref('')
  let controller: AbortController | undefined
  let timer: ReturnType<typeof setTimeout> | undefined
  let sequence = 0
  const filters = computed<StockFilters>(() => ({
    q: typeof route.query.q === 'string' ? route.query.q : '',
    supplier_id: route.query.supplier_id ? positive(route.query.supplier_id, 0) || null : null,
    category_id: route.query.category_id ? positive(route.query.category_id, 0) || null : null,
    stock: route.query.stock === 'eq:0' ? 'eq:0' : 'gt:0',
    page: positive(route.query.page, 1),
    page_size: [25, 50, 100].includes(Number(route.query.page_size)) ? Number(route.query.page_size) : 50,
  }))
  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / filters.value.page_size)))

  async function load(): Promise<void> {
    controller?.abort(); controller = new AbortController(); const current = ++sequence
    loading.value = true; error.value = ''
    try {
      const result = await listStock(filters.value, controller.signal)
      if (current !== sequence) return
      items.value = result.items; total.value = result.total
    } catch (cause) {
      if (current !== sequence) return
      const message = getHttpErrorMessage(cause, 'No se pudo cargar el stock')
      if (message) { error.value = message; items.value = []; total.value = 0 }
    } finally { if (current === sequence) loading.value = false }
  }

  async function setFilters(patch: Partial<StockFilters>, resetPage = true): Promise<void> {
    const next = { ...filters.value, ...patch }
    if (resetPage && !Object.prototype.hasOwnProperty.call(patch, 'page')) next.page = 1
    const query: Record<string, string> = { stock: next.stock }
    if (next.q.trim()) query.q = next.q.trim()
    if (next.supplier_id) query.supplier_id = String(next.supplier_id)
    if (next.category_id) query.category_id = String(next.category_id)
    if (next.page > 1) query.page = String(next.page)
    if (next.page_size !== 50) query.page_size = String(next.page_size)
    await router.replace({ query })
  }

  function schedule(): void { controller?.abort(); clearTimeout(timer); timer = setTimeout(load, debounceMs) }
  function retry(): void { clearTimeout(timer); void load() }
  function setTab(stock: StockTab): void { void setFilters({ stock }) }
  watch(filters, schedule, { immediate: true })
  onBeforeUnmount(() => { clearTimeout(timer); controller?.abort() })
  return { items, total, loading, error, filters, totalPages, setFilters, setTab, retry }
}
