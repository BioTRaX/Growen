<!-- NG-HEADER: Nombre de archivo: TechnicalDashboardView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/admin/views/TechnicalDashboardView.vue -->
<!-- NG-HEADER: Descripción: Dashboard técnico de monitoreo sin acciones operativas. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  getCatalogSummaries,
  getChatStats,
  getChatMetrics,
  getEnrichmentSummary,
  getImageJobStatus,
  getKnowledgeStatus,
  getSchedulerStatus,
  getTechnicalHealth,
  listDriveRuns,
  listKnowledgeTasks,
  listSchedulerRuns,
  type ChatStats,
  type ChatMetrics,
  type EnrichmentSummary,
  type HealthSummary,
} from '../../../services/adminOperations'
import { getHttpErrorMessage } from '../../../services/http'
import { getCatalogAuditSummary } from '../../catalog-audit/api/catalogAudit'
import type { CatalogAuditSummary } from '../../catalog-audit/types'

const health = ref<HealthSummary>()
const chat = ref<ChatStats>()
const chatMetrics = ref<ChatMetrics>()
const enrichment = ref<EnrichmentSummary>()
const catalogAudit = ref<CatalogAuditSummary>()
const operations = ref<Array<{ name: string; status: string; detail: string; to: string }>>([])
const loading = ref(false)
const error = ref('')
const cards = computed(() => Object.entries(health.value?.details ?? {}).filter(([key]) => !['optional', 'process'].includes(key)))
function isHealthy(value: unknown): boolean {
  if (typeof value !== 'object' || value === null) return Boolean(value)
  const record = value as Record<string, unknown>
  return record.ok === undefined ? true : Boolean(record.ok)
}
async function refresh(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const [healthResult, chatResult, metricsResult, drive, scheduler, schedulerRuns, catalogs, knowledge, knowledgeTasks, images, enrichSummary, auditSummary] = await Promise.all([
      getTechnicalHealth(), getChatStats(), getChatMetrics(), listDriveRuns(1), getSchedulerStatus(), listSchedulerRuns(),
      getCatalogSummaries(), getKnowledgeStatus(), listKnowledgeTasks(), getImageJobStatus(), getEnrichmentSummary(), getCatalogAuditSummary(),
    ])
    health.value = healthResult
    chat.value = chatResult
    chatMetrics.value = metricsResult
    enrichment.value = enrichSummary
    catalogAudit.value = auditSummary
    const imageState = String(images.status ?? images.state ?? (images.running ? 'running' : 'idle'))
    operations.value = [
      { name: 'Enrich v2', status: enrichSummary.worker.status ?? (enrichSummary.worker.ok ? 'running' : 'stopped'), detail: `${enrichSummary.worker.ready} en cola · ${enrichSummary.jobs.by_status.review_required ?? 0} pendientes de revisión · ${enrichSummary.catalog_coverage.enriched}/${enrichSummary.catalog_coverage.total_canonical} enriquecidos`, to: '/admin/servicios/workers' },
      { name: 'Auditor de catálogo', status: auditSummary.worker.status, detail: `${auditSummary.worker.ready} listos en Redis · ${auditSummary.runs.active} runs activos · ${auditSummary.catalog_coverage.audited}/${auditSummary.catalog_coverage.total_canonical} auditados`, to: '/admin/auditor-catalogo' },
      { name: 'Drive Sync', status: drive.items[0]?.status ?? 'sin ejecuciones', detail: drive.items[0]?.created_at ?? 'Sin historial', to: '/admin/drive-sync' },
      { name: 'Scheduler', status: scheduler.working ? 'running' : scheduler.enabled ? 'enabled' : 'disabled', detail: schedulerRuns.items[0]?.status ?? scheduler.next_run_time ?? 'Sin ejecuciones', to: '/admin/scheduler' },
      { name: 'Catálogos', status: catalogs[0]?.status ?? 'sin ejecuciones', detail: catalogs[0]?.generated_at ?? 'Sin historial', to: '/admin/catalogos-diagnostico' },
      { name: 'Conocimiento', status: knowledge.tasks_running ? 'running' : knowledge.files_pending ? 'pending' : 'ok', detail: `${knowledge.total_sources} fuentes · ${knowledgeTasks[0]?.status ?? 'sin tareas'}`, to: '/admin/conocimiento' },
      { name: 'Imágenes', status: imageState, detail: JSON.stringify(images).slice(0, 160), to: '/admin/imagenes-operacion' },
    ]
  }
  catch (reason) { error.value = getHttpErrorMessage(reason) }
  finally { loading.value = false }
}
onMounted(refresh)
</script>

<template>
  <v-container class="py-8" fluid>
    <div class="d-flex justify-space-between align-center mb-6"><div><h1 class="text-h4">Dashboard técnico</h1><p class="text-medium-emphasis mb-0">Monitoreo de solo lectura.</p></div><v-btn :loading="loading" variant="tonal" @click="refresh">Actualizar</v-btn></div>
    <v-alert v-if="error" class="mb-4" type="error">{{ error }}</v-alert>
    <v-alert class="mb-5" :type="health?.status === 'ok' ? 'success' : 'warning'" variant="tonal">Estado general: {{ health?.status ?? 'consultando' }}</v-alert>
    <v-row>
      <v-col v-for="([name, value]) in cards" :key="name" cols="12" sm="6" lg="4"><v-card class="h-100"><v-card-item :title="name"><template #prepend><v-icon :color="isHealthy(value) ? 'success' : 'warning'">{{ isHealthy(value) ? 'mdi-check-circle' : 'mdi-alert-circle' }}</v-icon></template></v-card-item><v-card-text><pre class="text-caption text-wrap">{{ JSON.stringify(value, null, 2) }}</pre></v-card-text></v-card></v-col>
      <v-col cols="12"><v-card><v-card-title>Chat</v-card-title><v-card-text class="d-flex flex-wrap ga-6"><span>Sesiones: {{ chat?.total_sessions ?? 0 }}</span><span>Mensajes: {{ chat?.total_messages ?? 0 }}</span><span>Últimos 7 días: {{ chat?.sessions_last_7_days ?? 0 }}</span><span>Promedio: {{ chat?.avg_messages_per_session ?? 0 }}</span></v-card-text><v-card-actions><v-btn to="/admin/chats" variant="text">Abrir Chat Inbox</v-btn><v-btn to="/admin/servicios" variant="text">Abrir Servicios</v-btn></v-card-actions></v-card></v-col>
      <v-col cols="12">
        <v-card>
          <v-card-item title="Auditor de catálogo">
            <template #prepend><v-icon :color="catalogAudit?.worker.ok ? 'success' : 'warning'">mdi-clipboard-search-outline</v-icon></template>
            <template #append><v-chip :color="catalogAudit?.worker.ok ? 'success' : 'warning'" size="small">Worker: {{ catalogAudit?.worker.status ?? 'stopped' }}</v-chip></template>
          </v-card-item>
          <v-card-text>
            <div class="d-flex flex-wrap ga-6 mb-4">
              <span><strong>Cola Redis:</strong> {{ catalogAudit?.worker.ready ?? 0 }} listos en Redis</span>
              <span><strong>Programados:</strong> {{ catalogAudit?.worker.delayed ?? 0 }}</span>
              <span><strong>Runs:</strong> {{ catalogAudit?.runs.by_status.queued ?? 0 }} encolado</span>
              <span>{{ (catalogAudit?.runs.by_status.running ?? 0) + (catalogAudit?.runs.by_status.waiting_enrich ?? 0) }} en curso</span>
              <span><strong>Ítems pendientes:</strong> {{ catalogAudit?.items.by_status.pending ?? 0 }}</span>
              <span><strong>Cobertura:</strong> {{ catalogAudit?.catalog_coverage.audited ?? 0 }} / {{ catalogAudit?.catalog_coverage.total_canonical ?? 0 }}</span>
            </div>
            <v-table v-if="catalogAudit?.runs.recent.length" density="compact">
              <thead><tr><th>Run</th><th>Estado</th><th>Progreso</th><th>Incidencias</th><th>Creado</th></tr></thead>
              <tbody>
                <tr v-for="run in catalogAudit.runs.recent" :key="run.run_id">
                  <td><code>{{ run.run_id }}</code></td>
                  <td><v-chip size="x-small">{{ run.status }}</v-chip></td>
                  <td>{{ run.processed_items }} / {{ run.total_items }}</td>
                  <td>{{ run.issue_items }}</td>
                  <td>{{ run.created_at ? new Date(run.created_at).toLocaleString('es-AR') : '—' }}</td>
                </tr>
              </tbody>
            </v-table>
            <v-empty-state v-else icon="mdi-clipboard-text-clock-outline" title="Sin auditorías registradas" />
          </v-card-text>
          <v-card-actions><v-btn to="/admin/auditor-catalogo" variant="text">Abrir auditor</v-btn><v-btn to="/admin/servicios/workers" variant="text">Ver worker</v-btn></v-card-actions>
        </v-card>
      </v-col>
      <v-col cols="12">
        <v-card>
          <v-card-item title="Enriquecimiento Canónico · Enrich v2">
            <template #prepend>
              <v-icon :color="enrichment?.worker.ok ? 'success' : 'warning'">mdi-auto-fix</v-icon>
            </template>
            <template #append>
              <v-chip
                :color="enrichment?.worker.ok ? 'success' : 'grey'"
                size="small"
                variant="flat"
              >
                Worker: {{ enrichment?.worker.status ?? 'stopped' }}
              </v-chip>
            </template>
          </v-card-item>
          <v-card-text>
            <div class="d-flex flex-wrap ga-6 mb-4">
              <span><strong>Cola Redis:</strong> {{ enrichment?.worker.ready ?? 0 }} pendientes (ready)</span>
              <span><strong>Programados:</strong> {{ enrichment?.worker.delayed ?? 0 }}</span>
              <span><strong>Total jobs:</strong> {{ enrichment?.jobs.total ?? 0 }}</span>
              <span><strong>Por revisar:</strong> {{ enrichment?.jobs.by_status?.review_required ?? 0 }}</span>
              <span><strong>Aplicados:</strong> {{ enrichment?.jobs.by_status?.applied ?? 0 }}</span>
              <span><strong>Fallidos:</strong> {{ enrichment?.jobs.by_status?.failed ?? 0 }}</span>
              <span>
                <strong>Cobertura de catálogo:</strong>
                {{ enrichment?.catalog_coverage.enriched ?? 0 }} / {{ enrichment?.catalog_coverage.total_canonical ?? 0 }}
                ({{ Math.round(((enrichment?.catalog_coverage.enriched ?? 0) / Math.max(1, enrichment?.catalog_coverage.total_canonical ?? 1)) * 100) }}%)
              </span>
            </div>

            <div v-if="enrichment?.jobs.recent && enrichment.jobs.recent.length > 0">
              <div class="text-subtitle-2 mb-2 text-medium-emphasis">Últimos jobs procesados:</div>
              <v-table density="compact">
                <thead>
                  <tr>
                    <th>Producto</th>
                    <th>Estado</th>
                    <th>Calidad</th>
                    <th>Advertencias</th>
                    <th>Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="job in enrichment.jobs.recent" :key="job.job_id">
                    <td class="font-weight-medium">{{ job.product_name }}</td>
                    <td><v-chip size="x-small">{{ job.status }}</v-chip></td>
                    <td>
                      <v-chip
                        v-if="job.quality_score !== null && job.quality_score !== undefined"
                        size="x-small"
                        :color="job.quality_score >= 80 ? 'success' : job.quality_score >= 50 ? 'warning' : 'error'"
                      >
                        {{ job.quality_score }}/100
                      </v-chip>
                      <span v-else class="text-caption text-medium-emphasis">—</span>
                    </td>
                    <td>
                      <span v-if="job.warnings_count > 0" class="text-warning text-caption">
                        {{ job.warnings_count }} advertencia(s)
                      </span>
                      <span v-else class="text-success text-caption">Sin alertas</span>
                    </td>
                    <td class="text-caption text-medium-emphasis">
                      {{ job.created_at ? new Date(job.created_at).toLocaleString('es-AR') : '—' }}
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </div>
          </v-card-text>
          <v-card-actions>
            <v-btn to="/admin/servicios/workers" variant="text">Ver Worker en Servicios</v-btn>
            <v-btn to="/productos/canonicos" variant="text">Ir a Productos Canónicos</v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
      <v-col cols="12"><v-card><v-card-title>Operaciones recientes</v-card-title><v-list><v-list-item v-for="operation in operations" :key="operation.name" :subtitle="operation.detail" :title="operation.name"><template #prepend><v-icon :color="['failed','error','disabled'].includes(operation.status) ? 'warning' : 'success'">mdi-chart-timeline-variant</v-icon></template><template #append><div class="d-flex align-center ga-2"><v-chip size="small">{{ operation.status }}</v-chip><v-btn :to="operation.to" icon="mdi-open-in-new" size="small" variant="text" /></div></template></v-list-item></v-list></v-card></v-col>
    </v-row>
  </v-container>
</template>
