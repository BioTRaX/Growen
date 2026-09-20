// NG-HEADER: Nombre de archivo: useShortages.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/stock/composables/useShortages.ts
// NG-HEADER: Descripción: Estado remoto, filtros URL y cancelación del listado de faltantes.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getHttpErrorMessage } from '../../../services/http'
import { getShortageStats, listShortages } from '../api/stock'
import type { ShortageItem, ShortageReason, ShortageStats } from '../types'

function positive(value: unknown, fallback: number): number {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback
}

function parseReason(value: unknown): ShortageReason | undefined {
  return value === 'GIFT' || value === 'PENDING_SALE' || value === 'UNKNOWN' ? value : undefined
}

export function useShortages() {
  const route = useRoute()
  const router = useRouter()
  const items = ref<ShortageItem[]>([])
  const stats = ref<ShortageStats | null>(null)
  const total = ref(0)
  const pages = ref(1)
  const loading = ref(false)
  const statsLoading = ref(false)
  const error = ref('')
  let controller: AbortController | undefined
  let sequence = 0

  const filters = computed(() => ({
    reason: parseReason(route.query.reason),
    page: positive(route.query.page, 1),
    page_size: 20,
  }))

  async function loadList(): Promise<void> {
    controller?.abort()
    controller = new AbortController()
    const current = ++sequence
    loading.value = true
    error.value = ''
    try {
      const result = await listShortages(filters.value, controller.signal)
      if (current !== sequence) return
      items.value = result.items
      total.value = result.total
      pages.value = Math.max(1, result.pages)
    } catch (cause) {
      if (current !== sequence) return
      const message = getHttpErrorMessage(cause, 'No se pudieron cargar los faltantes')
      if (message) {
        error.value = message
        items.value = []
        total.value = 0
      }
    } finally {
      if (current === sequence) loading.value = false
    }
  }

  async function loadStats(): Promise<void> {
    statsLoading.value = true
    try {
      stats.value = await getShortageStats()
    } catch (cause) {
      error.value = getHttpErrorMessage(cause, 'No se pudieron cargar las estadísticas')
    } finally {
      statsLoading.value = false
    }
  }

  async function setFilters(patch: { reason?: ShortageReason; page?: number }): Promise<void> {
    const nextReason = Object.prototype.hasOwnProperty.call(patch, 'reason') ? patch.reason : filters.value.reason
    const nextPage = Object.prototype.hasOwnProperty.call(patch, 'page') ? patch.page ?? 1 : 1
    const query: Record<string, string> = {}
    if (nextReason) query.reason = nextReason
    if (nextPage > 1) query.page = String(nextPage)
    await router.replace({ query })
  }

  async function refresh(): Promise<void> {
    await Promise.all([loadList(), loadStats()])
  }

  watch(filters, () => { void loadList() }, { immediate: true })
  void loadStats()
  onBeforeUnmount(() => controller?.abort())

  return { items, stats, total, pages, loading, statsLoading, error, filters, setFilters, refresh, retry: loadList }
}
