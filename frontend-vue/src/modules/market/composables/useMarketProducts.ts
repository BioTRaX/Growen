// NG-HEADER: Nombre de archivo: useMarketProducts.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/market/composables/useMarketProducts.ts
// NG-HEADER: Descripción: Listado paginado de Mercado con filtros URL y cancelación.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getHttpErrorMessage } from '../../../services/http'
import { listMarketProducts } from '../api/market'
import type { MarketFilters, MarketProduct } from '../types'

function positive(value: unknown, fallback: number): number { const parsed = Number(value); return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback }
export function useMarketProducts(debounceMs = 300) {
  const route = useRoute(); const router = useRouter(); const items = ref<MarketProduct[]>([]); const total = ref(0); const pages = ref(0); const loading = ref(false); const error = ref('')
  let controller: AbortController | undefined; let timer: ReturnType<typeof setTimeout> | undefined; let sequence = 0
  const filters = computed<MarketFilters>(() => ({ q: typeof route.query.q === 'string' ? route.query.q : '', category_id: route.query.category_id ? positive(route.query.category_id, 0) || null : null, supplier_id: route.query.supplier_id ? positive(route.query.supplier_id, 0) || null : null, page: positive(route.query.page, 1), page_size: [25, 50, 100].includes(Number(route.query.page_size)) ? Number(route.query.page_size) : 50 }))
  async function load() { controller?.abort(); controller = new AbortController(); const current = ++sequence; loading.value = true; error.value = ''; try { const result = await listMarketProducts(filters.value, controller.signal); if (current !== sequence) return; items.value = result.items; total.value = result.total; pages.value = result.pages } catch (cause) { if (current !== sequence) return; const message = getHttpErrorMessage(cause, 'No se pudo cargar Mercado'); if (message) error.value = message } finally { if (current === sequence) loading.value = false } }
  async function setFilters(patch: Partial<MarketFilters>, resetPage = true) { const next = { ...filters.value, ...patch }; if (resetPage && !Object.hasOwn(patch, 'page')) next.page = 1; const query: Record<string, string> = {}; if (next.q.trim()) query.q = next.q.trim(); if (next.category_id) query.category_id = String(next.category_id); if (next.supplier_id) query.supplier_id = String(next.supplier_id); if (next.page > 1) query.page = String(next.page); if (next.page_size !== 50) query.page_size = String(next.page_size); await router.replace({ query }) }
  function schedule() { controller?.abort(); clearTimeout(timer); timer = setTimeout(load, debounceMs) }
  watch(filters, schedule, { immediate: true }); onBeforeUnmount(() => { controller?.abort(); clearTimeout(timer) })
  return { items, total, pages, loading, error, filters, setFilters, refresh: load }
}
