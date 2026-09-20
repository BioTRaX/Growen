// NG-HEADER: Nombre de archivo: useMarketJob.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/market/composables/useMarketJob.ts
// NG-HEADER: Descripción: Polling cancelable de jobs de Mercado hasta estado terminal.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { onBeforeUnmount, ref } from 'vue'
import { getHttpErrorMessage } from '../../../services/http'
import { getMarketJob } from '../api/market'
import type { MarketJob } from '../types'
const terminal = new Set(['partial', 'succeeded', 'failed', 'cancelled'])
export function useMarketJob(intervalMs = 1500) {
  const job = ref<MarketJob | null>(null); const error = ref(''); let timer: ReturnType<typeof setTimeout> | undefined; let generation = 0
  function stop() { clearTimeout(timer); generation += 1 }
  async function follow(jobId: string) { stop(); const current = generation; error.value = ''; try { const result = await getMarketJob(jobId); if (current !== generation) return; job.value = result; if (!terminal.has(result.status)) timer = setTimeout(() => follow(jobId), intervalMs) } catch (cause) { if (current === generation) error.value = getHttpErrorMessage(cause, 'No se pudo consultar el job') } }
  onBeforeUnmount(stop); return { job, error, follow, stop }
}
