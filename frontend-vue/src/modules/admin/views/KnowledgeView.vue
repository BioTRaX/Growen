<!-- NG-HEADER: Nombre de archivo: KnowledgeView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/admin/views/KnowledgeView.vue -->
<!-- NG-HEADER: Descripción: Administración, clasificación y prueba del conocimiento RAG. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  deleteKnowledgeFile, deleteKnowledgeSource, getKnowledgeFiles, getKnowledgeSources,
  getKnowledgeStatus, indexKnowledge, listKnowledgeTasks, testRag, updateKnowledgeSourcePolicy,
  uploadKnowledge, type KnowledgeFile, type KnowledgeSource, type KnowledgeStatus,
  type KnowledgeTask, type RagResult,
} from '../../../services/adminOperations'
import { getHttpErrorMessage } from '../../../services/http'

const files = ref<KnowledgeFile[]>([])
const sources = ref<KnowledgeSource[]>([])
const tasks = ref<KnowledgeTask[]>([])
const status = ref<KnowledgeStatus | null>(null)
const results = ref<RagResult[]>([])
const query = ref('')
const loading = ref(false)
const error = ref('')
const roles = ['guest', 'cliente', 'proveedor', 'colaborador', 'admin']
const channels = ['web', 'websocket', 'telegram']

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    [files.value, sources.value, status.value, tasks.value] = await Promise.all([
      getKnowledgeFiles(), getKnowledgeSources(), getKnowledgeStatus(), listKnowledgeTasks(),
    ])
  } catch (e) { error.value = getHttpErrorMessage(e) } finally { loading.value = false }
}
async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  loading.value = true
  try { await uploadKnowledge(file); await refresh() }
  catch (e) { error.value = getHttpErrorMessage(e) }
  finally { input.value = ''; loading.value = false }
}
async function index(target: string, force = false) {
  loading.value = true
  try { await indexKnowledge(target, force); await refresh() }
  catch (e) { error.value = getHttpErrorMessage(e) }
  finally { loading.value = false }
}
async function remove(file: KnowledgeFile, removeFile = false) {
  loading.value = true
  try {
    if (removeFile) await deleteKnowledgeFile(file.path)
    else if (file.source_id) await deleteKnowledgeSource(file.source_id)
    await refresh()
  } catch (e) { error.value = getHttpErrorMessage(e) } finally { loading.value = false }
}
async function savePolicy(source: KnowledgeSource) {
  loading.value = true
  try {
    await updateKnowledgeSourcePolicy(source.id, {
      role_scope: source.role_scope, channel_scope: source.channel_scope,
      visibility: source.visibility, status: source.status, expires_at: source.expires_at || null,
    })
    await refresh()
  } catch (e) { error.value = getHttpErrorMessage(e) } finally { loading.value = false }
}
async function search() {
  if (!query.value.trim()) return
  loading.value = true
  try { results.value = await testRag(query.value) }
  catch (e) { error.value = getHttpErrorMessage(e) }
  finally { loading.value = false }
}
onMounted(refresh)
</script>

<template>
  <v-container fluid class="py-8">
    <div class="d-flex flex-wrap justify-space-between align-center ga-3 mb-6">
      <div><h1 class="text-h4">Conocimiento</h1><p class="text-medium-emphasis">RAG con acceso por rol, canal y vigencia</p></div>
      <div class="d-flex flex-wrap ga-2">
        <v-btn variant="tonal" :loading="loading" @click="refresh">Actualizar</v-btn>
        <v-btn color="primary" @click="index('folder')">Indexar pendientes</v-btn>
        <v-btn variant="tonal" @click="index('folder', true)">Reindexar todo</v-btn>
        <v-btn tag="label" prepend-icon="mdi-upload"><input type="file" accept=".md,.txt,.pdf" hidden @change="upload">Subir archivo</v-btn>
      </div>
    </div>
    <v-alert v-if="error" type="error" closable class="mb-4" @click:close="error = ''">{{ error }}</v-alert>
    <v-alert type="info" variant="tonal" class="mb-4">Las fuentes nuevas o migradas permanecen cerradas hasta guardar una política activa.</v-alert>
    <v-row class="mb-4">
      <v-col v-for="item in [{l:'Fuentes',v:status?.total_sources},{l:'Chunks',v:status?.total_chunks},{l:'Pendientes',v:status?.files_pending},{l:'Tareas activas',v:status?.tasks_running}]" :key="item.l" cols="6" md="3">
        <v-card><v-card-text><div class="text-caption">{{ item.l }}</div><div class="text-h5">{{ item.v ?? 0 }}</div></v-card-text></v-card>
      </v-col>
    </v-row>
    <v-card class="mb-4">
      <v-card-title>Políticas de fuentes</v-card-title>
      <v-card-text v-if="!sources.length" class="text-medium-emphasis">No hay fuentes indexadas.</v-card-text>
      <v-expansion-panels v-else>
        <v-expansion-panel v-for="source in sources" :key="source.id">
          <v-expansion-panel-title>
            <span class="text-truncate">{{ source.filename }}</span>
            <v-spacer/><v-chip size="small" :color="source.status === 'active' ? 'success' : source.status === 'stale' ? 'warning' : 'default'">{{ source.status }}</v-chip>
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-row>
              <v-col cols="12" md="6"><v-select v-model="source.role_scope" :items="roles" label="Roles" multiple chips/></v-col>
              <v-col cols="12" md="6"><v-select v-model="source.channel_scope" :items="channels" label="Canales" multiple chips/></v-col>
              <v-col cols="12" md="4"><v-select v-model="source.visibility" :items="['public','supplier','internal']" label="Visibilidad"/></v-col>
              <v-col cols="12" md="4"><v-select v-model="source.status" :items="['active','stale','disabled']" label="Estado"/></v-col>
              <v-col cols="12" md="4"><v-text-field v-model="source.expires_at" type="datetime-local" label="Vence (opcional)" clearable/></v-col>
            </v-row>
            <div class="d-flex justify-space-between align-center"><span class="text-caption">Versión {{ source.content_version }} · {{ source.chunks_count }} chunks</span><v-btn color="primary" :loading="loading" @click="savePolicy(source)">Guardar política</v-btn></div>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-card>
    <v-card>
      <v-card-title>Archivos</v-card-title>
      <v-data-table :items="files" :loading="loading" :headers="[{title:'Archivo',key:'filename'},{title:'Estado',key:'indexed'},{title:'Chunks',key:'chunks_count'},{title:'',key:'actions',sortable:false}]">
        <template #item.indexed="{ item }"><v-chip size="small" :color="item.needs_reindex ? 'warning' : item.indexed ? 'success' : 'default'">{{ item.needs_reindex ? 'Desactualizado' : item.indexed ? 'Indexado' : 'Pendiente' }}</v-chip></template>
        <template #item.actions="{ item }"><div class="d-flex ga-1 justify-end"><v-btn size="small" variant="text" @click="index(item.path,item.indexed)">Indexar</v-btn><v-btn v-if="item.source_id" size="small" variant="text" @click="remove(item)">Quitar índice</v-btn><v-btn size="small" color="error" variant="text" @click="remove(item,true)">Eliminar</v-btn></div></template>
      </v-data-table>
    </v-card>
    <v-row class="mt-4">
      <v-col cols="12" lg="6"><v-card><v-card-title>Probar recuperación</v-card-title><v-card-text><v-textarea v-model="query" label="Síntomas o consulta" rows="3"/><v-btn color="primary" @click="search">Buscar contexto</v-btn><v-list><v-list-item v-for="result in results" :key="`${result.source}-${result.chunk_index}`" :title="`${result.source} · ${(result.similarity*100).toFixed(1)}%`" :subtitle="result.content"/></v-list></v-card-text></v-card></v-col>
      <v-col cols="12" lg="6"><v-card><v-card-title>Tareas recientes</v-card-title><v-list><v-list-item v-for="task in tasks" :key="task.id" :title="`${task.type}: ${task.target}`" :subtitle="`${task.status} · ${task.progress}%${task.error ? ` · ${task.error}` : ''}`"/></v-list></v-card></v-col>
    </v-row>
  </v-container>
</template>
