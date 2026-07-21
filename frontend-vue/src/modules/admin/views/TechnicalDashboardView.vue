<!-- NG-HEADER: Nombre de archivo: TechnicalDashboardView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/admin/views/TechnicalDashboardView.vue -->
<!-- NG-HEADER: Descripción: Dashboard técnico de monitoreo sin acciones operativas. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  getCatalogSummaries,
  getChatStats,
  getImageJobStatus,
  getKnowledgeStatus,
  getSchedulerStatus,
  getTechnicalHealth,
  listDriveRuns,
  listKnowledgeTasks,
  listSchedulerRuns,
  type ChatStats,
  type HealthSummary,
} from '../../../services/adminOperations'
import { getHttpErrorMessage } from '../../../services/http'

const health = ref<HealthSummary>()
const chat = ref<ChatStats>()
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
    const [healthResult, chatResult, drive, scheduler, schedulerRuns, catalogs, knowledge, knowledgeTasks, images] = await Promise.all([
      getTechnicalHealth(), getChatStats(), listDriveRuns(1), getSchedulerStatus(), listSchedulerRuns(),
      getCatalogSummaries(), getKnowledgeStatus(), listKnowledgeTasks(), getImageJobStatus(),
    ])
    health.value = healthResult
    chat.value = chatResult
    const imageState = String(images.status ?? images.state ?? (images.running ? 'running' : 'idle'))
    operations.value = [
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
      <v-col cols="12"><v-card><v-card-title>Operaciones recientes</v-card-title><v-list><v-list-item v-for="operation in operations" :key="operation.name" :subtitle="operation.detail" :title="operation.name"><template #prepend><v-icon :color="['failed','error','disabled'].includes(operation.status) ? 'warning' : 'success'">mdi-chart-timeline-variant</v-icon></template><template #append><div class="d-flex align-center ga-2"><v-chip size="small">{{ operation.status }}</v-chip><v-btn :to="operation.to" icon="mdi-open-in-new" size="small" variant="text" /></div></template></v-list-item></v-list></v-card></v-col>
    </v-row>
  </v-container>
</template>
