<!-- NG-HEADER: Nombre de archivo: McpToolsView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/admin/views/McpToolsView.vue -->
<!-- NG-HEADER: Descripción: Estado y control de servidores MCP para administradores. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { getHttpErrorMessage } from '../../../services/http'
import { mcpHealth, startMcp, stopMcp, type McpServer } from '../../../services/adminServices'
import { useToastStore } from '../../../app/notifications/store'

const rows = ref<McpServer[]>([])
const context = ref('')
const loading = ref(false)
const busy = ref('')
const error = ref('')
const toasts = useToastStore()
let timer: ReturnType<typeof setInterval> | undefined

async function refresh() {
  loading.value = true
  try { const data = await mcpHealth(); rows.value = data.servers ?? []; context.value = data.context ?? '' }
  catch (exception) { error.value = getHttpErrorMessage(exception, 'No se pudo consultar MCP') }
  finally { loading.value = false }
}

async function toggle(server: McpServer) {
  busy.value = server.name; error.value = ''
  try {
    const result = server.status === 'running' ? await stopMcp(server.name) : await startMcp(server.name)
    toasts.show(result.message ?? 'Operación solicitada', result.ok === false ? 'warning' : 'success')
    await refresh()
  } catch (exception) { error.value = getHttpErrorMessage(exception) }
  finally { busy.value = '' }
}

onMounted(() => { void refresh(); timer = setInterval(refresh, 15000) })
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <v-container fluid class="py-8">
    <div class="d-flex justify-space-between align-center mb-6"><div><h1 class="text-h4">MCP Tools</h1><p class="text-medium-emphasis">Contexto detectado: {{ context || '—' }}</p></div><v-btn prepend-icon="mdi-refresh" :loading="loading" @click="refresh">Actualizar</v-btn></div>
    <v-alert v-if="error" type="error" closable class="mb-4" @click:close="error=''">{{ error }}</v-alert>
    <v-row><v-col v-for="server in rows" :key="server.name" cols="12" lg="6"><v-card>
      <v-card-title class="d-flex align-center"><v-icon :color="server.healthy?'success':server.status==='running'?'warning':'error'" icon="mdi-circle" size="small" class="mr-3" />{{ server.label }}</v-card-title>
      <v-card-text><v-chip size="small" :color="server.healthy?'success':'warning'">{{ server.status }}</v-chip><span class="ml-3 text-medium-emphasis">Puerto {{ server.port }} · {{ server.tool_count ?? 0 }} tools</span><p v-if="server.error" class="text-error mt-3">{{ server.error }}</p><p class="text-caption mt-3">{{ server.resolved_url || server.url }}</p></v-card-text>
      <v-card-actions><v-btn :color="server.status==='running'?'error':'primary'" :loading="busy===server.name" @click="toggle(server)">{{ server.status==='running'?'Detener':'Iniciar' }}</v-btn></v-card-actions>
    </v-card></v-col></v-row>
    <v-empty-state v-if="!loading && !rows.length" icon="mdi-lan-disconnect" title="No hay servidores MCP configurados" />
  </v-container>
</template>
