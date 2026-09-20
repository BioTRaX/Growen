<!-- NG-HEADER: Nombre de archivo: CatalogDiagnosticsView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/admin/views/CatalogDiagnosticsView.vue -->
<!-- NG-HEADER: Descripción: Historial y diagnóstico persistente de generación de catálogos. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { useAuthStore } from '../../../auth/store'
import { downloadCatalogLog, getCatalogLog, getCatalogStatus, getCatalogSummaries, unlockCatalog, type CatalogLog, type CatalogSummary } from '../../../services/adminOperations'
import { getHttpErrorMessage } from '../../../services/http'

const auth = useAuthStore()
const status = ref<Record<string, unknown>>({})
const summaries = ref<CatalogSummary[]>([])
const log = ref<CatalogLog[]>([])
const selectedId = ref('')
const loading = ref(false)
const error = ref('')
function idOf(summary: CatalogSummary): string { return summary.run_id }
async function refresh(): Promise<void> {
  loading.value = true
  try { [status.value, summaries.value] = await Promise.all([getCatalogStatus(), getCatalogSummaries()]) }
  catch (reason) { error.value = getHttpErrorMessage(reason) }
  finally { loading.value = false }
}
async function select(summary: CatalogSummary): Promise<void> {
  selectedId.value = idOf(summary)
  try { log.value = await getCatalogLog(selectedId.value) }
  catch (reason) { error.value = getHttpErrorMessage(reason) }
}
async function unlock(): Promise<void> { try { await unlockCatalog(); await refresh() } catch (reason) { error.value = getHttpErrorMessage(reason) } }
onMounted(refresh)
</script>

<template>
  <v-container class="py-8" fluid>
    <div class="d-flex flex-wrap justify-space-between align-center ga-3 mb-6"><div><h1 class="text-h4">Diagnóstico de catálogos</h1><p class="text-medium-emphasis mb-0">Ejecuciones, duraciones y eventos descargables.</p></div><div class="d-flex ga-2"><v-btn v-if="auth.role === 'admin'" color="warning" variant="tonal" @click="unlock">Desbloquear</v-btn><v-btn :loading="loading" @click="refresh">Actualizar</v-btn></div></div>
    <v-alert v-if="error" class="mb-4" closable type="error" @click:close="error = ''">{{ error }}</v-alert>
    <v-card class="mb-5"><v-card-title>Estado actual</v-card-title><v-card-text><pre>{{ JSON.stringify(status, null, 2) }}</pre></v-card-text></v-card>
    <v-row><v-col cols="12" lg="5"><v-card><v-card-title>Historial</v-card-title><v-data-table :items="summaries" :headers="[{title:'Fecha',key:'generated_at'},{title:'Productos',key:'count'},{title:'Duración',key:'duration_ms'},{title:'',key:'actions'}]" density="compact"><template #item.generated_at="{ item }">{{ new Date(item.generated_at).toLocaleString() }}</template><template #item.duration_ms="{ item }">{{ item.duration_ms }} ms</template><template #item.actions="{ item }"><v-btn size="small" variant="text" @click="select(item)">Eventos</v-btn></template></v-data-table></v-card></v-col><v-col cols="12" lg="7"><v-card><v-card-title>Eventos {{ selectedId }}</v-card-title><v-card-actions v-if="selectedId"><v-btn size="small" @click="downloadCatalogLog(selectedId, 'ndjson')">NDJSON</v-btn><v-btn size="small" @click="downloadCatalogLog(selectedId, 'csv')">CSV</v-btn></v-card-actions><v-table density="compact"><thead><tr><th>Fecha</th><th>Etapa</th><th>Detalle</th></tr></thead><tbody><tr v-for="(event, index) in log" :key="index"><td>{{ event.ts }}</td><td>{{ event.step }}</td><td><code>{{ JSON.stringify(event) }}</code></td></tr></tbody></v-table><v-empty-state v-if="!log.length" title="Seleccioná una ejecución" /></v-card></v-col></v-row>
  </v-container>
</template>
