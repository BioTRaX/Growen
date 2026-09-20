<!-- NG-HEADER: Nombre de archivo: ChatView.vue -->
<!-- NG-HEADER: Ubicación: frontend-vue/src/modules/chat/views/ChatView.vue -->
<!-- NG-HEADER: Descripción: Chat 😎 multicanal con WebSocket y fallback HTTP. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import { useAuthStore } from '../../../auth/store'
import { classifyHttpError, getHttpErrorMessage } from '../../../services/http'
import { openWebSocket } from '../../../services/transports'
import { chatProducts, sendChat, sendChatFeedback, type ChatCitation, type ChatProduct, type ChatProductData } from '../api/chat'
import TelegramIdentityPanel from '../components/TelegramIdentityPanel.vue'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  text: string
  products?: ChatProduct[]
  citations?: ChatCitation[]
  correlationId?: string
  streamId?: string
  feedback?: 'positive' | 'negative'
}

const auth = useAuthStore()
const draft = ref('')
const imageUrl = ref('')
const messages = ref<Message[]>([])
const sending = ref(false)
const connection = ref<'connecting' | 'connected' | 'fallback' | 'offline'>('connecting')
const error = ref('')
const messageList = ref<HTMLElement>()
let socket: WebSocket | undefined
let reconnectTimer: number | undefined
let reconnectAttempt = 0
let stopped = false
let controller: AbortController | undefined

const canAttachImage = computed(() => ['colaborador', 'admin'].includes(auth.role))
const canViewOperationalFields = computed(() => ['colaborador', 'admin'].includes(auth.role))
const statusColor = computed(() => ({ connecting: 'warning', connected: 'success', fallback: 'info', offline: 'error' })[connection.value])

function scheduleReconnect(): void {
  if (stopped || reconnectTimer) return
  reconnectAttempt += 1
  const delay = Math.min(30_000, 500 * (2 ** reconnectAttempt))
  reconnectTimer = window.setTimeout(() => { reconnectTimer = undefined; connect() }, delay)
}

function connect(): void {
  if (stopped) return
  connection.value = 'connecting'
  try {
    socket = openWebSocket('/ws')
    socket.onopen = () => { reconnectAttempt = 0; connection.value = 'connected' }
    socket.onclose = () => {
      connection.value = 'fallback'
      if (sending.value) {
        sending.value = false
        error.value = 'La conexión se interrumpió antes de recibir la respuesta. Podés volver a intentar.'
      }
      scheduleReconnect()
    }
    socket.onerror = () => { connection.value = 'fallback' }
    socket.onmessage = (event) => {
      let complete = true
      try {
        const payload = JSON.parse(String(event.data)) as { role?: string; text?: string; type?: string; stream?: 'start'|'chunk'|'end'|'error'; id?: string; correlation_id?: string; data?: ChatProductData; citations?: ChatCitation[] }
        if (payload.role !== 'assistant' && payload.role !== 'system') return
        complete = payload.stream !== 'start' && payload.stream !== 'chunk'
        const streamed = payload.id ? messages.value.find((message) => message.streamId === payload.id) : undefined
        if (payload.stream === 'start' && payload.id) messages.value.push({ id: crypto.randomUUID(), streamId: payload.id, role: 'assistant', text: '' })
        else if (payload.stream === 'chunk' && streamed) streamed.text += payload.text ?? ''
        else if (payload.stream === 'end' && streamed) { streamed.text = payload.text ?? streamed.text; streamed.citations = payload.citations; streamed.correlationId = payload.correlation_id }
        else if (payload.stream === 'error' && streamed) { streamed.text = 'No pude completar la respuesta.'; streamed.correlationId = payload.correlation_id }
        else messages.value.push({ id: crypto.randomUUID(), role: payload.role, text: payload.text ?? '', products: chatProducts(payload.data), citations: payload.citations, correlationId: payload.correlation_id })
      } catch {
        messages.value.push({ id: crypto.randomUUID(), role: 'assistant', text: String(event.data) })
      } finally {
        if (complete) sending.value = false
        scrollToEnd()
      }
    }
  } catch {
    connection.value = 'fallback'
    scheduleReconnect()
  }
}

async function submit(): Promise<void> {
  const text = draft.value.trim()
  if (!text || sending.value) return
  error.value = ''
  messages.value.push({ id: crypto.randomUUID(), role: 'user', text })
  draft.value = ''
  sending.value = true
  await scrollToEnd()

  if (socket?.readyState === WebSocket.OPEN && !imageUrl.value) {
    socket.send(text)
    return
  }
  connection.value = navigator.onLine ? 'fallback' : 'offline'
  controller = new AbortController()
  try {
    const response = await sendChat(text, canAttachImage.value ? imageUrl.value.trim() || undefined : undefined, controller.signal)
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'assistant',
      text: response.data.text,
      products: chatProducts(response.data.data),
      citations: response.data.citations,
      correlationId: response.correlationId,
    })
    imageUrl.value = ''
  } catch (caught) {
    if (classifyHttpError(caught) !== 'cancelled') error.value = getHttpErrorMessage(caught, 'No pude obtener una respuesta')
  } finally {
    sending.value = false
    controller = undefined
    await scrollToEnd()
  }
}

function cancel(): void {
  controller?.abort()
  if (socket?.readyState === WebSocket.OPEN) socket.close(1000, 'cancelled')
  sending.value = false
}

async function feedback(message: Message, rating: 'positive' | 'negative'): Promise<void> {
  if (!message.correlationId) return
  await sendChatFeedback(message.correlationId, rating)
  message.feedback = rating
}

function productPrice(product: ChatProduct): string | undefined {
  if (product.formatted_price) return product.formatted_price
  const value = product.sale_price ?? product.price
  if (value === undefined || value === null) return undefined
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: product.currency || 'ARS' }).format(value)
}

function productAvailability(product: ChatProduct): string | undefined {
  if (product.availability) return product.availability
  if (product.stock_status === 'ok') return 'Disponible'
  if (product.stock_status === 'low') return 'Disponibilidad limitada'
  if (product.stock_status === 'out') return 'Sin disponibilidad inmediata'
  return undefined
}

async function scrollToEnd(): Promise<void> {
  await nextTick()
  messageList.value?.scrollTo({ top: messageList.value.scrollHeight, behavior: 'smooth' })
}

onMounted(async () => {
  await auth.hydrate()
  if (!auth.isAuthenticated) await auth.loginAsGuest()
  connect()
})
onBeforeUnmount(() => {
  stopped = true
  controller?.abort()
  if (reconnectTimer) window.clearTimeout(reconnectTimer)
  socket?.close(1000, 'unmount')
})
</script>

<template>
  <v-container class="chat-page py-6" fluid>
    <TelegramIdentityPanel />
    <v-card class="chat-card mx-auto" max-width="1080" rounded="xl">
      <v-card-title class="d-flex align-center justify-space-between ga-3 flex-wrap pa-5">
        <div><div class="text-h5">Chat 😎</div><div class="text-body-2 text-medium-emphasis">Asistente Growen</div></div>
        <v-chip :color="statusColor" size="small" variant="tonal"><v-icon start icon="mdi-circle" size="10" />{{ connection }}</v-chip>
      </v-card-title>
      <v-divider />
      <section ref="messageList" class="messages pa-4" aria-live="polite" aria-label="Conversación">
        <v-alert v-if="!messages.length" type="info" variant="tonal">Preguntame por productos, cultivo o documentación disponible para tu rol.</v-alert>
        <article v-for="message in messages" :key="message.id" class="message" :class="`message--${message.role}`">
          <div class="message__bubble">{{ message.text }}</div>
          <v-row v-if="message.products?.length" dense class="mt-2">
            <v-col v-for="product in message.products" :key="product.product_id ?? product.name ?? product.title" cols="12" sm="6">
              <v-card variant="tonal"><v-card-title class="text-subtitle-1">{{ product.name ?? product.title }}</v-card-title><v-card-text><div v-if="productPrice(product)">{{ productPrice(product) }}</div><div v-if="productAvailability(product)">{{ productAvailability(product) }}</div><div v-if="canViewOperationalFields && product.sku" class="text-caption">SKU {{ product.sku }}</div><div v-if="canViewOperationalFields && (product.stock ?? product.stock_qty) !== undefined" class="text-caption">Stock {{ product.stock ?? product.stock_qty }}</div><div v-if="canViewOperationalFields && product.supplier_name" class="text-caption">Proveedor {{ product.supplier_name }}</div></v-card-text></v-card>
            </v-col>
          </v-row>
          <v-expansion-panels v-if="message.citations?.length" class="mt-2" variant="accordion">
            <v-expansion-panel title="Fuentes"><v-expansion-panel-text><v-list density="compact"><v-list-item v-for="citation in message.citations" :key="`${citation.source_id}-${citation.chunk_index}`" :title="citation.title" :subtitle="`Fragmento ${citation.chunk_index}${citation.page ? ` · pág. ${citation.page}` : ''} · v${citation.content_version}`" /></v-list></v-expansion-panel-text></v-expansion-panel>
          </v-expansion-panels>
          <div v-if="message.role === 'assistant' && message.correlationId" class="d-flex ga-1 mt-1"><v-btn icon="mdi-thumb-up-outline" size="x-small" variant="text" :color="message.feedback === 'positive' ? 'success' : undefined" aria-label="Respuesta útil" @click="feedback(message, 'positive')" /><v-btn icon="mdi-thumb-down-outline" size="x-small" variant="text" :color="message.feedback === 'negative' ? 'error' : undefined" aria-label="Respuesta no útil" @click="feedback(message, 'negative')" /></div>
        </article>
        <v-progress-linear v-if="sending" indeterminate color="primary" class="mt-3" />
      </section>
      <v-divider />
      <v-card-text class="pa-4">
        <v-alert v-if="error" type="error" closable class="mb-3" @click:close="error = ''">{{ error }}</v-alert>
        <v-text-field v-if="canAttachImage" v-model="imageUrl" label="URL de imagen (opcional)" prepend-inner-icon="mdi-image-outline" clearable />
        <div class="d-flex align-end ga-2"><v-textarea v-model="draft" label="Escribí tu consulta" auto-grow rows="1" max-rows="6" maxlength="2000" counter hide-details="auto" @keydown.ctrl.enter.prevent="submit" /><v-btn v-if="sending" color="error" icon="mdi-stop" aria-label="Cancelar" @click="cancel" /><v-btn v-else color="primary" icon="mdi-send" aria-label="Enviar" :disabled="!draft.trim()" @click="submit" /></div>
        <div class="text-caption text-medium-emphasis mt-2">Ctrl + Enter para enviar. El borrador vive sólo en memoria.</div>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<style scoped>
.chat-page{min-height:calc(100vh - 64px)}.chat-card{overflow:hidden}.messages{height:min(62vh,720px);overflow-y:auto}.message{display:flex;flex-direction:column;align-items:flex-start;margin:12px 0}.message--user{align-items:flex-end}.message__bubble{max-width:min(78ch,88%);padding:12px 16px;border-radius:18px;background:rgb(var(--v-theme-surface-variant));white-space:pre-wrap;overflow-wrap:anywhere}.message--user .message__bubble{background:rgb(var(--v-theme-primary));color:rgb(var(--v-theme-on-primary))}@media(max-width:600px){.messages{height:56vh}.message__bubble{max-width:94%}}
</style>
