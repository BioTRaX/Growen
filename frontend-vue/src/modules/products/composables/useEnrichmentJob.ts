// NG-HEADER: Nombre de archivo: useEnrichmentJob.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/composables/useEnrichmentJob.ts
// NG-HEADER: Descripción: Estado y polling cancelable de un job Enrich v2.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { onBeforeUnmount, ref } from 'vue'

import { getHttpErrorMessage } from '../../../services/http'
import {
  applyEnrichmentJob,
  createEnrichmentJob,
  discardEnrichmentJob,
  getEnrichmentJob,
} from '../api/products'
import type { EnrichmentJob, EnrichmentScope } from '../types'

const TERMINAL = new Set(['review_required', 'partially_applied', 'applied', 'failed', 'cancelled', 'discarded'])

export function useEnrichmentJob(onContentChanged: () => Promise<void>) {
  const job = ref<EnrichmentJob | null>(null)
  const loading = ref(false)
  const error = ref('')
  let timer: ReturnType<typeof setTimeout> | undefined
  let cancelled = false

  function stopPolling(): void {
    cancelled = true
    if (timer) clearTimeout(timer)
    timer = undefined
  }

  async function poll(canonicalId: number, jobId: string): Promise<void> {
    if (cancelled) return
    try {
      job.value = await getEnrichmentJob(canonicalId, jobId)
      if (!TERMINAL.has(job.value.status)) {
        timer = setTimeout(() => void poll(canonicalId, jobId), 1500)
      }
    } catch (cause) {
      error.value = getHttpErrorMessage(cause, 'No se pudo consultar el progreso')
    }
  }

  async function start(canonicalId: number, productId: number, scope: EnrichmentScope): Promise<void> {
    stopPolling()
    cancelled = false
    loading.value = true
    error.value = ''
    try {
      const created = await createEnrichmentJob(canonicalId, productId, scope)
      await poll(canonicalId, created.job_id)
    } catch (cause) {
      error.value = getHttpErrorMessage(cause, 'No se pudo iniciar el enriquecimiento')
    } finally {
      loading.value = false
    }
  }

  async function apply(canonicalId: number, revision: number, fields: string[]): Promise<void> {
    if (!job.value) return
    loading.value = true
    error.value = ''
    try {
      await applyEnrichmentJob(canonicalId, job.value.job_id, fields, revision)
      job.value = await getEnrichmentJob(canonicalId, job.value.job_id)
      await onContentChanged()
    } catch (cause) {
      error.value = getHttpErrorMessage(cause, 'No se pudieron aplicar los campos')
    } finally {
      loading.value = false
    }
  }

  async function discard(canonicalId: number): Promise<void> {
    if (!job.value) return
    loading.value = true
    error.value = ''
    try {
      await discardEnrichmentJob(canonicalId, job.value.job_id)
      job.value = await getEnrichmentJob(canonicalId, job.value.job_id)
    } catch (cause) {
      error.value = getHttpErrorMessage(cause, 'No se pudo descartar la propuesta')
    } finally {
      loading.value = false
    }
  }

  onBeforeUnmount(stopPolling)
  return { job, loading, error, start, apply, discard, stopPolling }
}
