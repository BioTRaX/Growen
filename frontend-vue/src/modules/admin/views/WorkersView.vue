<!-- NG-HEADER: Nombre de archivo: WorkersView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/admin/views/WorkersView.vue -->
<!-- NG-HEADER: Descripción: Control de workers, health, dependencias, logs y streaming SSE. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { useToastStore } from '../../../app/notifications/store'
import { hasCapabilities } from '../../../auth/capabilities'
import { useAuthStore } from '../../../auth/store'
import {
  checkServiceDependencies, deleteServiceLogs, installServiceDependencies, listAdminServices,
  panicStopServices, serviceHealth, serviceLogs, serviceLogStream, setServiceAutoStart,
  startAdminService, stopAdminService, type AdminService, type ServiceLog,
} from '../../../services/adminServices'
import { getHttpErrorMessage } from '../../../services/http'

const labels: Record<string, string> = {
  pdf_import: 'Importador PDF (OCR)', playwright: 'Playwright / Chromium', image_processing: 'Procesamiento de imágenes',
  dramatiq: 'Dramatiq / Redis', scheduler: 'Scheduler', notifier: 'Notificaciones', market_worker: 'Worker Mercado',
  drive_sync_worker: 'Worker Drive Sync', telegram_polling_worker: 'Worker Telegram', catalog_worker: 'Worker Catálogo',
}
const auth = useAuthStore()
const toasts = useToastStore()
const rows = ref<AdminService[]>([])
const logs = ref<Record<string, ServiceLog[]>>({})
const health = ref<Record<string, { ok: boolean; hints?: string[] }>>({})
const busy = ref('')
const loading = ref(false)
const error = ref('')
const confirmPanic = ref(false)
const confirmDelete = ref<string>()
const driveMode = ref<'docker' | 'local'>('docker')
const streams = new Map<string, EventSource>()
const canInstall = computed(() => hasCapabilities(auth.role, ['services.dependencies.install']))

function statusColor(status: string) { return status === 'running' ? 'success' : status === 'starting' || status === 'degraded' ? 'warning' : 'error' }
function uptime(seconds?: number | null) { if (!seconds) return '—'; const h = Math.floor(seconds / 3600); const m = Math.floor(seconds % 3600 / 60); return `${h}h ${m}m` }

async function refresh() {
  loading.value = true; error.value = ''
  try { rows.value = (await listAdminServices()).sort((a, b) => a.name.localeCompare(b.name)) }
  catch (exception) { error.value = getHttpErrorMessage(exception, 'No se pudieron cargar los workers') }
  finally { loading.value = false }
}
async function run(name: string, action: () => Promise<unknown>) {
  busy.value = name; error.value = ''
  try { await action(); toasts.show('Operación completada', 'success'); await refresh() }
  catch (exception) { error.value = getHttpErrorMessage(exception) }
  finally { busy.value = '' }
}
async function start(row: AdminService) { await run(row.name, () => startAdminService(row.name, row.name === 'drive_sync_worker' ? driveMode.value : undefined)) }
async function stop(row: AdminService) { await run(row.name, () => stopAdminService(row.name)) }
async function autoStart(row: AdminService, value: boolean | null) { await run(row.name, () => setServiceAutoStart(row.name, !!value)) }
async function loadDetails(row: AdminService) {
  try {
    const [recent, state] = await Promise.all([serviceLogs(row.name), serviceHealth(row.name)])
    logs.value[row.name] = recent; health.value[row.name] = state
  } catch (exception) { error.value = getHttpErrorMessage(exception, `No se pudo consultar ${row.name}`) }
}
function toggleStream(row: AdminService) {
  const current = streams.get(row.name)
  if (current) { current.close(); streams.delete(row.name); toasts.show('Streaming detenido', 'info'); return }
  const lastId = logs.value[row.name]?.at(-1)?.id ?? 0
  const stream = serviceLogStream(row.name, lastId)
  stream.onmessage = (event) => { try { const item = JSON.parse(event.data) as ServiceLog; logs.value[row.name] = [...(logs.value[row.name] ?? []), item].slice(-200) } catch { /* evento inválido */ } }
  stream.onerror = () => { stream.close(); streams.delete(row.name); toasts.show(`Stream de ${labels[row.name] ?? row.name} interrumpido`, 'warning') }
  streams.set(row.name, stream); toasts.show('Streaming de logs conectado', 'success')
}
async function checkDeps(row: AdminService) { try { const result = await checkServiceDependencies(row.name); toasts.show(result.ok ? 'Dependencias correctas' : `Faltan: ${(result.missing ?? []).join(', ')}`, result.ok ? 'success' : 'warning') } catch (e) { error.value = getHttpErrorMessage(e) } }
async function installDeps(row: AdminService) { await run(row.name, () => installServiceDependencies(row.name)) }
async function panic() { confirmPanic.value = false; await run('panic', panicStopServices) }
async function removeLogs() { const name = confirmDelete.value; confirmDelete.value = undefined; if (!name) return; await run(name, async () => { await deleteServiceLogs(name); logs.value[name] = [] }) }

onMounted(refresh)
onBeforeUnmount(() => { streams.forEach((stream) => stream.close()); streams.clear() })
</script>

<template>
  <v-container fluid class="py-8">
    <div class="d-flex justify-space-between align-center flex-wrap ga-3 mb-6"><div><h1 class="text-h4">Workers</h1><p class="text-medium-emphasis">Estado, ejecución, dependencias y logs operativos</p></div><div class="d-flex ga-2"><v-btn prepend-icon="mdi-refresh" :loading="loading" @click="refresh">Actualizar</v-btn><v-btn color="error" prepend-icon="mdi-alert-octagon" @click="confirmPanic=true">Panic stop</v-btn></div></div>
    <v-alert v-if="error" type="error" closable class="mb-4" @click:close="error=''">{{ error }}</v-alert>
    <v-expansion-panels variant="accordion">
      <v-expansion-panel v-for="row in rows" :key="row.name" @group:selected="(event) => { if (event.value) loadDetails(row) }">
        <v-expansion-panel-title><div class="d-flex align-center ga-3 flex-grow-1"><v-icon icon="mdi-circle" size="small" :color="statusColor(row.status)" /><strong>{{ labels[row.name] ?? row.name }}</strong><v-chip size="x-small" :color="statusColor(row.status)">{{ row.status }}</v-chip><span class="text-caption text-medium-emphasis">uptime {{ uptime(row.uptime_s) }}</span></div></v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-alert v-if="row.last_error" type="warning" variant="tonal" class="mb-4">{{ row.last_error }}</v-alert>
          <div class="d-flex align-center flex-wrap ga-2 mb-4">
            <v-select v-if="row.name==='drive_sync_worker' && row.status!=='running'" v-model="driveMode" :items="['docker','local']" label="Modo" density="compact" hide-details max-width="160" />
            <v-btn v-if="row.status!=='running'" color="primary" :loading="busy===row.name" @click="start(row)">Iniciar</v-btn><v-btn v-else color="error" :loading="busy===row.name" @click="stop(row)">Detener</v-btn>
            <v-switch :model-value="row.auto_start" label="Inicio automático" hide-details density="compact" @update:model-value="(value) => autoStart(row,value)" />
            <v-btn variant="tonal" @click="checkDeps(row)">Validar dependencias</v-btn><v-btn v-if="canInstall" variant="tonal" color="warning" :loading="busy===row.name" @click="installDeps(row)">Instalar dependencias</v-btn>
            <v-btn variant="text" @click="loadDetails(row)">Actualizar detalle</v-btn><v-btn variant="text" @click="toggleStream(row)">{{ streams.has(row.name) ? 'Detener stream' : 'Logs en vivo' }}</v-btn>
            <v-btn v-if="row.status!=='running'" variant="text" color="error" @click="confirmDelete=row.name">Eliminar historial DB</v-btn>
          </div>
          <div v-if="health[row.name]" class="mb-3"><v-chip :color="health[row.name].ok?'success':'error'">Health {{ health[row.name].ok?'OK':'FALLA' }}</v-chip><span v-if="health[row.name].hints?.length" class="ml-3 text-warning">{{ health[row.name].hints?.join(' · ') }}</span></div>
          <v-table density="compact" fixed-header height="280"><thead><tr><th>Fecha</th><th>Nivel</th><th>Acción</th><th>CID</th><th>Resultado</th></tr></thead><tbody><tr v-for="(entry,index) in logs[row.name] ?? []" :key="entry.id ?? index"><td>{{ entry.created_at ?? '—' }}</td><td>{{ entry.level ?? '—' }}</td><td>{{ entry.action }}</td><td><code>{{ entry.cid }}</code></td><td :class="entry.ok?'text-success':'text-error'">{{ entry.ok?'OK':entry.error ?? 'Error' }}</td></tr></tbody></v-table>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
    <v-empty-state v-if="!loading && !rows.length" title="No hay workers configurados" icon="mdi-cog-off-outline" />
    <v-dialog v-model="confirmPanic" max-width="480"><v-card><v-card-title>Detener servicios no esenciales</v-card-title><v-card-text>Esta acción puede interrumpir procesos en curso. FastAPI y la base permanecerán disponibles.</v-card-text><v-card-actions><v-spacer/><v-btn @click="confirmPanic=false">Cancelar</v-btn><v-btn color="error" @click="panic">Confirmar</v-btn></v-card-actions></v-card></v-dialog>
    <v-dialog :model-value="!!confirmDelete" max-width="480" @update:model-value="(value) => { if (!value) confirmDelete=undefined }"><v-card><v-card-title>Eliminar historial del worker</v-card-title><v-card-text>Se eliminarán únicamente los registros <code>ServiceLog</code> persistidos de {{ confirmDelete }}. Los archivos físicos y carpetas de ejecución se administran desde Servicios → Mantenimiento de logs.</v-card-text><v-card-actions><v-spacer/><v-btn @click="confirmDelete=undefined">Cancelar</v-btn><v-btn color="error" @click="removeLogs">Eliminar historial</v-btn></v-card-actions></v-card></v-dialog>
  </v-container>
</template>
