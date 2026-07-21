<!-- NG-HEADER: Nombre de archivo: ImageOperationsView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/admin/views/ImageOperationsView.vue -->
<!-- NG-HEADER: Descripción: Operación administrativa del crawler y jobs de imágenes. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { cleanImageLogs, downloadImageLogs, getImageJobStatus, listImageSnapshots, openImageJobEvents, probeImageCrawler, saveImageJobSettings, triggerImageCrawl, triggerImagePurge } from '../../../services/adminOperations'
import { getHttpErrorMessage } from '../../../services/http'

const status = ref<Record<string, unknown>>({})
const liveLogs = ref<string[]>([])
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const probeTitle = ref('')
const probeResult = ref<Record<string, unknown>>()
const correlationId = ref('')
const snapshots = ref<Array<{ name: string; size: number; mtime: number }>>([])
const confirmLogCleanup = ref(false)
const settings = ref({ active: false, mode: 'off', retries: 2, rate_rps: 1, burst: 2, log_retention_days: 30, purge_ttl_days: 30 })
let stream: EventSource | undefined
const progress = computed(() => status.value.progress as { percent?: number; processed?: number; total?: number } | undefined)
const storedLogs = computed(() => Array.isArray(status.value.logs) ? status.value.logs as Array<{ level?: string; message?: string; created_at?: string }> : [])

async function refresh(): Promise<void> {
  loading.value = true
  try { status.value = await getImageJobStatus(); settings.value = { ...settings.value, ...((status.value.settings as Partial<typeof settings.value>) ?? {}) } }
  catch (reason) { error.value = getHttpErrorMessage(reason) }
  finally { loading.value = false }
}
async function execute(action: () => Promise<unknown>): Promise<void> {
  busy.value = true
  try { await action(); await refresh() }
  catch (reason) { error.value = getHttpErrorMessage(reason) }
  finally { busy.value = false }
}
async function probe(): Promise<void> { if (!probeTitle.value) return; try { probeResult.value = await probeImageCrawler(probeTitle.value) as Record<string, unknown> } catch (reason) { error.value = getHttpErrorMessage(reason) } }
async function loadSnapshots(): Promise<void> { try { snapshots.value = await listImageSnapshots(correlationId.value) } catch (reason) { error.value = getHttpErrorMessage(reason) } }
async function cleanupOperationalLogs(): Promise<void> {
  confirmLogCleanup.value = false
  await execute(async () => {
    await cleanImageLogs()
    liveLogs.value = []
    snapshots.value = []
  })
}
onMounted(() => {
  void refresh()
  stream = openImageJobEvents()
  stream.onmessage = (event) => { liveLogs.value.unshift(event.data); liveLogs.value = liveLogs.value.slice(0, 100) }
})
onUnmounted(() => stream?.close())
</script>

<template>
  <v-container class="py-8" fluid>
    <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-6">
      <div><h1 class="text-h4">Operación de imágenes</h1><p class="text-medium-emphasis mb-0">Crawler, cola, snapshots y observabilidad.</p></div>
      <div class="d-flex ga-2"><v-btn to="/admin/servicios" variant="text">Ir a Servicios</v-btn><v-btn :loading="loading" variant="tonal" @click="refresh">Actualizar</v-btn></div>
    </div>
    <v-alert v-if="error" class="mb-4" closable type="error" @click:close="error = ''">{{ error }}</v-alert>
    <v-row>
      <v-col cols="12" md="4"><v-card class="h-100"><v-card-title>Estado</v-card-title><v-card-text><v-chip :color="status.running ? 'success' : 'warning'" class="mb-4">{{ status.running ? 'Procesando' : 'Detenido' }}</v-chip><div>Pendientes: {{ status.pending ?? 0 }}</div><div>Correctos: {{ status.ok ?? 0 }}</div><div>Fallidos: {{ status.fail ?? 0 }}</div><v-progress-linear class="mt-4" :model-value="progress?.percent ?? 0" height="12" rounded /><small>{{ progress?.processed ?? 0 }} / {{ progress?.total ?? 0 }}</small></v-card-text></v-card></v-col>
      <v-col cols="12" md="8"><v-card class="h-100"><v-card-title>Acciones y configuración</v-card-title><v-card-text class="d-flex flex-wrap ga-3"><v-btn color="primary" :loading="busy" @click="execute(() => triggerImageCrawl('stock'))">Buscar faltantes</v-btn><v-btn color="warning" :loading="busy" variant="tonal" @click="execute(triggerImagePurge)">Ejecutar purga</v-btn><v-btn variant="tonal" @click="downloadImageLogs">Descargar logs</v-btn><v-btn color="error" :loading="busy" variant="text" @click="confirmLogCleanup = true">Limpiar logs operativos</v-btn></v-card-text><v-card-text><v-row><v-col cols="6" md="3"><v-select v-model="settings.mode" :items="['off','on','window']" label="Modo" /></v-col><v-col cols="6" md="3"><v-number-input v-model="settings.retries" label="Reintentos" :min="0" /></v-col><v-col cols="6" md="3"><v-number-input v-model="settings.rate_rps" label="RPS" :min="0.1" :step="0.1" /></v-col><v-col cols="6" md="3"><v-number-input v-model="settings.purge_ttl_days" label="TTL purga" :min="1" /></v-col></v-row><v-btn variant="tonal" @click="execute(() => saveImageJobSettings(settings))">Guardar configuración</v-btn></v-card-text><v-card-text class="text-medium-emphasis">El inicio y detención de Playwright y workers se realiza desde Servicios.</v-card-text></v-card></v-col>
      <v-col cols="12" md="6"><v-card><v-card-title>Prueba del crawler</v-card-title><v-card-text><v-text-field v-model="probeTitle" label="Título del producto" append-inner-icon="mdi-magnify" @click:append-inner="probe" @keyup.enter="probe" /><pre v-if="probeResult">{{ JSON.stringify(probeResult, null, 2) }}</pre></v-card-text></v-card></v-col>
      <v-col cols="12" md="6"><v-card><v-card-title>Snapshots</v-card-title><v-card-text><v-text-field v-model="correlationId" label="Correlation ID" append-inner-icon="mdi-magnify" @click:append-inner="loadSnapshots" @keyup.enter="loadSnapshots" /><v-list density="compact"><v-list-item v-for="snapshot in snapshots" :key="snapshot.name" :title="snapshot.name" :subtitle="`${snapshot.size} bytes`" /></v-list></v-card-text></v-card></v-col>
      <v-col cols="12"><v-card><v-card-title>Logs</v-card-title><v-list density="compact" max-height="440" class="overflow-y-auto"><v-list-item v-for="(line, index) in liveLogs" :key="`live-${index}`" prepend-icon="mdi-access-point"><v-list-item-title class="text-mono">{{ line }}</v-list-item-title></v-list-item><v-list-item v-for="(line, index) in storedLogs" :key="`stored-${index}`"><v-list-item-title>[{{ line.level }}] {{ line.message }}</v-list-item-title><v-list-item-subtitle>{{ line.created_at }}</v-list-item-subtitle></v-list-item></v-list><v-empty-state v-if="!liveLogs.length && !storedLogs.length" icon="mdi-text-box-search-outline" title="Sin logs recientes" /></v-card></v-col>
    </v-row>
    <v-dialog v-model="confirmLogCleanup" max-width="520"><v-card title="Limpiar logs de Imágenes"><v-card-text>Se eliminarán el historial persistido del crawler, <code>logs/image_crawler.ndjson</code> y los snapshots de <code>tmp/crawl</code>. Esta acción no afecta las carpetas de <code>start-dev</code>.</v-card-text><v-card-actions><v-spacer/><v-btn @click="confirmLogCleanup=false">Cancelar</v-btn><v-btn color="error" :loading="busy" @click="cleanupOperationalLogs">Limpiar</v-btn></v-card-actions></v-card></v-dialog>
  </v-container>
</template>
