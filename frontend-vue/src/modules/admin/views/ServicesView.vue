<!-- NG-HEADER: Nombre de archivo: ServicesView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/admin/views/ServicesView.vue -->
<!-- NG-HEADER: Descripción: Resumen operativo de workers y servidores MCP. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../../../auth/store'
import { useToastStore } from '../../../app/notifications/store'
import { getHttpErrorMessage } from '../../../services/http'
import { cleanPhysicalLogs, listAdminServices, mcpHealth, previewPhysicalLogCleanup, type AdminService, type LogCleanupPlan, type McpServer } from '../../../services/adminServices'

const auth = useAuthStore()
const toasts = useToastStore()
const router = useRouter()
const workers = ref<AdminService[]>([])
const servers = ref<McpServer[]>([])
const loading = ref(false)
const error = ref('')
const cleanupKeepDays = ref(7)
const cleanupPlan = ref<LogCleanupPlan>()
const cleanupDialog = ref(false)
const cleanupBusy = ref(false)
const workersOnline = computed(() => workers.value.filter((item) => item.status === 'running').length)
const mcpOnline = computed(() => servers.value.filter((item) => item.status === 'running' && item.healthy).length)

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    workers.value = await listAdminServices()
    if (auth.role === 'admin') servers.value = (await mcpHealth()).servers ?? []
  } catch (exception) {
    error.value = getHttpErrorMessage(exception, 'No se pudo cargar el estado de servicios')
  } finally {
    loading.value = false
  }
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`
}

async function previewCleanup() {
  cleanupBusy.value = true; error.value = ''
  try { cleanupPlan.value = await previewPhysicalLogCleanup(cleanupKeepDays.value); cleanupDialog.value = true }
  catch (exception) { error.value = getHttpErrorMessage(exception, 'No se pudo previsualizar la limpieza') }
  finally { cleanupBusy.value = false }
}

async function executeCleanup() {
  cleanupBusy.value = true; error.value = ''
  try {
    const response = await cleanPhysicalLogs(cleanupKeepDays.value)
    cleanupPlan.value = response.plan
    cleanupDialog.value = false
    toasts.show(`Se eliminaron ${response.result.removed_directories} carpetas y ${response.result.removed_files} archivos`, response.result.ok ? 'success' : 'warning')
  } catch (exception) { error.value = getHttpErrorMessage(exception, 'No se pudo limpiar los logs') }
  finally { cleanupBusy.value = false }
}

onMounted(refresh)
</script>

<template>
  <v-container fluid class="py-8">
    <div class="d-flex justify-space-between align-center mb-6">
      <div><h1 class="text-h4">Servicios</h1><p class="text-medium-emphasis">Workers y herramientas MCP del entorno Growen</p></div>
      <v-btn prepend-icon="mdi-refresh" :loading="loading" @click="refresh">Actualizar</v-btn>
    </div>
    <v-alert v-if="error" type="error" closable class="mb-4" @click:close="error=''">{{ error }}</v-alert>
    <v-row>
      <v-col cols="12" md="6">
        <v-card height="100%" hover @click="router.push('/admin/servicios/workers')">
          <v-card-title><v-icon icon="mdi-cog-sync-outline" class="mr-2" />Workers</v-card-title>
          <v-card-text><div class="text-h3">{{ workersOnline }} <span class="text-h6 text-medium-emphasis">/ {{ workers.length }}</span></div><p class="mt-2">Procesamiento, scheduler, sincronizaciones y notificaciones.</p></v-card-text>
          <v-card-actions><v-btn color="primary">Administrar workers</v-btn></v-card-actions>
        </v-card>
      </v-col>
      <v-col v-if="auth.role === 'admin'" cols="12" md="6">
        <v-card height="100%" hover @click="router.push('/admin/servicios/mcp-tools')">
          <v-card-title><v-icon icon="mdi-lan-connect" class="mr-2" />MCP Tools</v-card-title>
          <v-card-text><div class="text-h3">{{ mcpOnline }} <span class="text-h6 text-medium-emphasis">/ {{ servers.length }}</span></div><p class="mt-2">Servidores de herramientas para productos y búsqueda web.</p></v-card-text>
          <v-card-actions><v-btn color="primary">Administrar MCP</v-btn></v-card-actions>
        </v-card>
      </v-col>
      <v-col v-if="auth.role === 'admin'" cols="12">
        <v-card>
          <v-card-title><v-icon icon="mdi-broom" class="mr-2" />Mantenimiento de logs físicos</v-card-title>
          <v-card-text><p>Elimina carpetas completas de ejecuciones antiguas en <code>logs/dev</code> y logs legacy. Preserva la ejecución activa o más reciente, reportes de bugs, sus capturas y el historial de Catálogos.</p><v-number-input v-model="cleanupKeepDays" class="mt-3" label="Conservar los últimos días" :min="0" :max="3650" max-width="280" /></v-card-text>
          <v-card-actions><v-btn color="warning" prepend-icon="mdi-eye-outline" :loading="cleanupBusy" @click="previewCleanup">Previsualizar limpieza</v-btn></v-card-actions>
        </v-card>
      </v-col>
    </v-row>
    <v-dialog v-model="cleanupDialog" max-width="720"><v-card title="Confirmar limpieza de logs"><v-card-text v-if="cleanupPlan"><v-alert type="warning" variant="tonal" class="mb-4">Esta operación elimina archivos y carpetas, pero nunca la ejecución activa o más reciente.</v-alert><p><strong>{{ cleanupPlan.target_count }}</strong> objetivos · <strong>{{ cleanupPlan.dev_run_directories }}</strong> carpetas de ejecución · <strong>{{ humanSize(cleanupPlan.bytes_reclaimable) }}</strong> recuperables.</p><v-list density="compact" max-height="300" class="overflow-y-auto"><v-list-item v-for="target in cleanupPlan.targets" :key="target.path" :title="target.path" :subtitle="target.reason"><template #prepend><v-icon :icon="target.kind === 'directory' ? 'mdi-folder-remove-outline' : 'mdi-file-remove-outline'" /></template></v-list-item></v-list><p class="text-caption mt-3">Protegidos: {{ cleanupPlan.protected.length }}</p></v-card-text><v-card-actions><v-spacer/><v-btn @click="cleanupDialog=false">Cancelar</v-btn><v-btn color="error" :loading="cleanupBusy" :disabled="!cleanupPlan?.target_count" @click="executeCleanup">Eliminar objetivos</v-btn></v-card-actions></v-card></v-dialog>
  </v-container>
</template>
