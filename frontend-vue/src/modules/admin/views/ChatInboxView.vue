<!-- NG-HEADER: Nombre de archivo: ChatInboxView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/admin/views/ChatInboxView.vue -->
<!-- NG-HEADER: Descripción: Inbox de conversaciones, feedback y gestión supervisada de prompts. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { useAuthStore } from '../../../auth/store'
import { activatePrompt, approvePrompt, bulkUpdateChats, classifyChat, createPromptCandidate, evaluatePrompt, getChat, getChatQualityMetrics, listChats, listChatStaff, listPromptVersions, saveChatFeedback, updateChat, type ChatDetail, type ChatQualityMetrics, type ChatSession, type PromptVersion, type StaffUser } from '../../../services/adminOperations'
import { getHttpErrorMessage } from '../../../services/http'

const auth = useAuthStore()
const sessions = ref<ChatSession[]>([])
const detail = ref<ChatDetail>()
const quality = ref<ChatQualityMetrics>()
const prompts = ref<PromptVersion[]>([])
const staff = ref<StaffUser[]>([])
const selectedSessions = ref<string[]>([])
const bulkStatus = ref('reviewed')
const total = ref(0)
const loading = ref(false)
const error = ref('')
const filters = ref({ q: '', user_identifier: '', status: '', channel: '', assigned_user_id: undefined as number | undefined, detected_intent: '', sentiment: '', tag: '', date_from: '', date_to: '' })
const notes = ref('')
const tagsText = ref('')
const promptDialog = ref(false)
const candidate = ref({ prompt_key: 'persona.observer', content: '', reason: '' })
const evaluationDialog = ref(false)
const evaluationTarget = ref<PromptVersion>()
const evaluation = ref({ dataset_version: 'review-set-v1', sample_count: 50, composite_score: 0.8, safety_passed: false })

async function refresh(): Promise<void> {
  loading.value = true
  try {
    const params = Object.fromEntries(Object.entries(filters.value).filter(([, value]) => value))
    const [page, metrics, staffRows] = await Promise.all([listChats(params), getChatQualityMetrics(), listChatStaff()])
    sessions.value = page.items; total.value = page.total; quality.value = metrics; staff.value = staffRows
    if (auth.role === 'admin') prompts.value = await listPromptVersions()
  } catch (reason) { error.value = getHttpErrorMessage(reason) }
  finally { loading.value = false }
}
async function open(session: ChatSession): Promise<void> {
  try { detail.value = await getChat(session.session_id); notes.value = detail.value.session.admin_notes ?? ''; tagsText.value = Object.keys(detail.value.session.tags ?? {}).join(', ') }
  catch (reason) { error.value = getHttpErrorMessage(reason) }
}
async function saveSession(): Promise<void> {
  if (!detail.value) return
  const tags = Object.fromEntries(tagsText.value.split(',').map((tag) => tag.trim()).filter(Boolean).map((tag) => [tag, true]))
  try { await updateChat(detail.value.session.session_id, { admin_notes: notes.value, tags, status: detail.value.session.status, assigned_user_id: detail.value.session.assigned_user_id }); await refresh() }
  catch (reason) { error.value = getHttpErrorMessage(reason) }
}
async function classify(): Promise<void> { if (detail.value) { await classifyChat(detail.value.session.session_id); window.setTimeout(() => void open(detail.value!.session), 500) } }
async function feedback(messageId: number, rating: 'positive' | 'negative'): Promise<void> { try { await saveChatFeedback(messageId, { rating, categories: [] }); await refresh() } catch (reason) { error.value = getHttpErrorMessage(reason) } }
async function createCandidate(): Promise<void> { try { await createPromptCandidate({ ...candidate.value, manual: true }); promptDialog.value = false; prompts.value = await listPromptVersions() } catch (reason) { error.value = getHttpErrorMessage(reason) } }
async function promote(prompt: PromptVersion): Promise<void> { try { if (prompt.status === 'candidate') { evaluationTarget.value = prompt; evaluationDialog.value = true; return } await activatePrompt(prompt.id); prompts.value = await listPromptVersions() } catch (reason) { error.value = getHttpErrorMessage(reason) } }
async function evaluateAndApprove(): Promise<void> { if (!evaluationTarget.value) return; try { await evaluatePrompt(evaluationTarget.value.id, { ...evaluation.value, details: {} }); await approvePrompt(evaluationTarget.value.id); evaluationDialog.value = false; prompts.value = await listPromptVersions() } catch (reason) { error.value = getHttpErrorMessage(reason) } }
async function applyBulk(): Promise<void> { if (!selectedSessions.value.length) return; try { await bulkUpdateChats(selectedSessions.value, { status: bulkStatus.value }); selectedSessions.value = []; await refresh() } catch (reason) { error.value = getHttpErrorMessage(reason) } }
onMounted(refresh)
</script>

<template>
  <v-container class="py-8" fluid>
    <div class="d-flex flex-wrap justify-space-between align-center ga-3 mb-6"><div><h1 class="text-h4">Chat Inbox</h1><p class="text-medium-emphasis mb-0">Revisión, clasificación y mejora supervisada.</p></div><div class="d-flex ga-2"><v-btn v-if="auth.role === 'admin'" @click="promptDialog = true">Nuevo candidato</v-btn><v-btn :loading="loading" variant="tonal" @click="refresh">Actualizar</v-btn></div></div>
    <v-alert v-if="error" class="mb-4" closable type="error" @click:close="error = ''">{{ error }}</v-alert>
    <v-row class="mb-3"><v-col cols="12" sm="4"><v-text-field v-model="filters.q" clearable label="Buscar" @keyup.enter="refresh" /></v-col><v-col cols="6" sm="2"><v-select v-model="filters.status" clearable :items="['new','reviewed','archived']" label="Estado" /></v-col><v-col cols="6" sm="2"><v-select v-model="filters.channel" clearable :items="['web','telegram']" label="Canal" /></v-col><v-col cols="6" sm="2"><v-select v-model="filters.sentiment" clearable :items="['positive','neutral','negative']" label="Sentimiento" /></v-col><v-col cols="6" sm="2"><v-btn block class="mt-2" @click="refresh">Filtrar</v-btn></v-col></v-row>
    <v-row class="mb-3"><v-col cols="12" sm="3"><v-text-field v-model="filters.user_identifier" clearable label="Usuario" /></v-col><v-col cols="12" sm="3"><v-select v-model="filters.assigned_user_id" clearable :items="staff" item-title="name" item-value="id" label="Responsable" /></v-col><v-col cols="6" sm="2"><v-text-field v-model="filters.detected_intent" clearable label="Intención" /></v-col><v-col cols="6" sm="2"><v-text-field v-model="filters.tag" clearable label="Tag" /></v-col><v-col cols="6" sm="2"><v-text-field v-model="filters.date_from" clearable label="Desde" type="date" /></v-col><v-col cols="6" sm="2"><v-text-field v-model="filters.date_to" clearable label="Hasta" type="date" /></v-col></v-row>
    <v-card v-if="detail?.trace" class="mb-3" variant="tonal"><v-card-title class="text-subtitle-1">Trazabilidad segura</v-card-title><v-card-text class="d-flex flex-wrap ga-2"><v-chip size="small">CID {{ detail.trace.correlation_id }}</v-chip><v-chip size="small">{{ detail.trace.account_role }} → {{ detail.trace.effective_role }}</v-chip><v-chip size="small">{{ detail.trace.channel }}</v-chip><v-chip size="small">{{ detail.trace.latency_ms ?? 0 }} ms</v-chip><v-chip size="small">{{ detail.trace.citation_count }} citas</v-chip><v-chip v-for="tool in detail.trace.tools" :key="`${tool.name}-${tool.status}`" size="small" :color="tool.status === 'succeeded' ? 'success' : 'warning'">{{ tool.name }} · {{ tool.status }}</v-chip></v-card-text></v-card>
    <v-row><v-col cols="12" lg="4"><v-card><v-card-title>Conversaciones ({{ total }})</v-card-title><v-card-text class="d-flex ga-2"><v-select v-model="bulkStatus" :items="['new','reviewed','archived']" density="compact" hide-details label="Acción masiva"/><v-btn :disabled="!selectedSessions.length" @click="applyBulk">Aplicar</v-btn></v-card-text><v-list lines="three"><v-list-item v-for="session in sessions" :key="session.session_id" :active="detail?.session.session_id === session.session_id" @click="open(session)"><template #prepend><v-checkbox-btn v-model="selectedSessions" :value="session.session_id" @click.stop /></template><v-list-item-title>{{ session.user_identifier }}</v-list-item-title><v-list-item-subtitle>{{ session.channel }} · {{ session.status }} · {{ session.message_count }} mensajes</v-list-item-subtitle><template #append><v-chip v-if="session.sentiment" size="x-small">{{ session.sentiment }}</v-chip></template></v-list-item></v-list><v-empty-state v-if="!sessions.length" title="Sin conversaciones" /></v-card></v-col>
      <v-col cols="12" lg="8"><v-card v-if="detail"><v-card-item :title="detail.session.user_identifier" :subtitle="`${detail.session.channel} · ${detail.session.detected_intent ?? 'sin clasificar'}`"><template #append><v-btn size="small" variant="tonal" @click="classify">Clasificar</v-btn></template></v-card-item><v-divider /><v-card-text class="messages"><div v-for="message in detail.messages" :key="message.id" class="mb-4"><v-chip class="mb-1" size="x-small">{{ message.role }}</v-chip><div class="message pa-3 rounded">{{ message.content }}</div><div v-if="message.role === 'assistant'" class="d-flex ga-1 mt-1"><v-btn icon="mdi-thumb-up-outline" size="x-small" variant="text" @click="feedback(message.id, 'positive')" /><v-btn icon="mdi-thumb-down-outline" size="x-small" variant="text" @click="feedback(message.id, 'negative')" /></div></div></v-card-text><v-divider /><v-card-text><v-select v-model="detail.session.status" :items="['new','reviewed','archived']" label="Estado" /><v-select v-model="detail.session.assigned_user_id" clearable :items="staff" item-title="name" item-value="id" label="Responsable" /><v-text-field v-model="tagsText" label="Tags separados por coma" /><v-textarea v-model="notes" label="Notas internas" rows="3" /></v-card-text><v-card-actions><v-spacer /><v-btn color="primary" @click="saveSession">Guardar revisión</v-btn></v-card-actions></v-card><v-card v-else><v-empty-state icon="mdi-chat-search-outline" title="Seleccioná una conversación" /></v-card></v-col></v-row>
    <v-card class="mt-6"><v-card-title>Métricas de calidad</v-card-title><v-card-text class="d-flex flex-wrap ga-6"><span>Feedback total: {{ quality?.total_feedback ?? 0 }}</span><span>Positivos: {{ quality?.feedback.positive ?? 0 }}</span><span>Negativos: {{ quality?.feedback.negative ?? 0 }}</span><span>Intenciones: {{ Object.keys(quality?.intents ?? {}).length }}</span><span>Sentimientos: {{ Object.keys(quality?.sentiments ?? {}).length }}</span></v-card-text></v-card>
    <v-card v-if="auth.role === 'admin'" class="mt-6"><v-card-title>Versiones de prompts</v-card-title><v-data-table :items="prompts" :headers="[{title:'Clave',key:'prompt_key'},{title:'Versión',key:'version'},{title:'Estado',key:'status'},{title:'Métricas',key:'metrics'},{title:'',key:'actions'}]"><template #item.metrics="{ item }"><code>{{ JSON.stringify(item.metrics) }}</code></template><template #item.actions="{ item }"><v-btn v-if="['candidate','approved','retired'].includes(item.status)" size="small" variant="text" @click="promote(item)">{{ item.status === 'candidate' ? 'Aprobar' : 'Activar' }}</v-btn></template></v-data-table></v-card>
    <v-dialog v-model="promptDialog" max-width="760"><v-card title="Crear candidato de prompt"><v-card-text><v-select v-model="candidate.prompt_key" :items="['persona.observer','persona.cultivator','persona.salesman','persona.asistente']" label="Persona" /><v-textarea v-model="candidate.content" label="Contenido" rows="12" /><v-text-field v-model="candidate.reason" label="Motivo" /></v-card-text><v-card-actions><v-spacer /><v-btn variant="text" @click="promptDialog = false">Cancelar</v-btn><v-btn color="primary" @click="createCandidate">Crear candidato</v-btn></v-card-actions></v-card></v-dialog>
    <v-dialog v-model="evaluationDialog" max-width="560"><v-card title="Evaluar candidato"><v-card-text><v-text-field v-model="evaluation.dataset_version" label="Versión del conjunto" /><v-number-input v-model="evaluation.sample_count" label="Muestras" :min="1" /><v-number-input v-model="evaluation.composite_score" label="Métrica compuesta" :min="0" :max="1" :step="0.01" /><v-checkbox v-model="evaluation.safety_passed" label="Sin regresiones de seguridad" /></v-card-text><v-card-actions><v-spacer /><v-btn variant="text" @click="evaluationDialog = false">Cancelar</v-btn><v-btn color="primary" :disabled="!evaluation.safety_passed" @click="evaluateAndApprove">Evaluar y aprobar</v-btn></v-card-actions></v-card></v-dialog>
  </v-container>
</template>

<style scoped>.messages{max-height:55vh;overflow:auto}.message{background:rgba(var(--v-theme-on-surface),.06);white-space:pre-wrap}</style>
