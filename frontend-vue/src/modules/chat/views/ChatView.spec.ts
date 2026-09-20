// NG-HEADER: Nombre de archivo: ChatView.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/chat/views/ChatView.spec.ts
// NG-HEADER: Descripción: Pruebas de streaming y cards sanitizadas de Chat 😎.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { vuetify } from '../../../app/providers/vuetify'
import { useAuthStore } from '../../../auth/store'

const transport = vi.hoisted(() => ({ openWebSocket: vi.fn() }))
const chatApi = vi.hoisted(() => ({
  sendChat: vi.fn(),
  sendChatFeedback: vi.fn(),
  chatProducts: (data?: { results?: unknown[]; products?: unknown[]; items?: unknown[] }) => data?.results ?? data?.products ?? data?.items,
}))
vi.mock('../../../services/transports', () => transport)
vi.mock('../api/chat', () => chatApi)

import ChatView from './ChatView.vue'

interface FakeSocket {
  readyState: number
  onopen?: () => void
  onclose?: () => void
  onerror?: () => void
  onmessage?: (event: { data: string }) => void
  send: ReturnType<typeof vi.fn>
  close: ReturnType<typeof vi.fn>
}

let socket: FakeSocket

function mountChat(role: 'cliente' | 'colaborador' = 'cliente') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.hydrated = true
  auth.isAuthenticated = true
  auth.role = role
  auth.user = { id: 2, identifier: 'chat-user', role }
  return mount(ChatView, { global: { plugins: [pinia, vuetify], stubs: { TelegramIdentityPanel: true } } })
}

describe('ChatView', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', { configurable: true, value: vi.fn() })
    socket = { readyState: 1, send: vi.fn(), close: vi.fn() }
    transport.openWebSocket.mockReturnValue(socket)
    chatApi.sendChatFeedback.mockResolvedValue(undefined)
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.unstubAllGlobals()
    delete (HTMLElement.prototype as { scrollTo?: unknown }).scrollTo
  })

  it('compone un único mensaje durante start/chunk/end y conserva correlation ID', async () => {
    const wrapper = mountChat()
    await flushPromises()
    socket.onmessage?.({ data: JSON.stringify({ role: 'assistant', stream: 'start', id: 'stream-1' }) })
    socket.onmessage?.({ data: JSON.stringify({ role: 'assistant', stream: 'chunk', id: 'stream-1', text: 'Hola ' }) })
    socket.onmessage?.({ data: JSON.stringify({ role: 'assistant', stream: 'chunk', id: 'stream-1', text: 'mundo' }) })
    socket.onmessage?.({ data: JSON.stringify({ role: 'assistant', stream: 'end', id: 'stream-1', text: 'Hola mundo', correlation_id: 'cid-1', citations: [{ source_id: 1, title: 'Guía', chunk_index: 0, page: 2, score: 0.9, content_version: 1 }] }) })
    await flushPromises()

    expect(wrapper.findAll('.message--assistant')).toHaveLength(1)
    expect(wrapper.text()).toContain('Hola mundo')
    expect(wrapper.text()).toContain('Fuentes')
    expect(wrapper.find('[aria-label="Respuesta útil"]').exists()).toBe(true)
  })

  it('oculta SKU y stock exacto a clientes incluso si el transporte los devuelve', async () => {
    socket.readyState = 3
    chatApi.sendChat.mockResolvedValue({
      data: { text: 'Disponible', type: 'product_answer', data: { results: [{ name: 'Producto', price: 100, currency: 'ARS', formatted_price: '$ 100', stock_status: 'ok', sku: 'SECRETO', stock_qty: 9, supplier_name: 'Interno' }] } },
      correlationId: 'cid-http',
    })
    const wrapper = mountChat('cliente')
    await flushPromises()
    await wrapper.get('textarea').setValue('precio')
    await wrapper.get('[aria-label="Enviar"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Producto')
    expect(wrapper.text()).toContain('$ 100')
    expect(wrapper.text()).toContain('Disponible')
    expect(wrapper.text()).not.toContain('SECRETO')
    expect(wrapper.text()).not.toContain('Stock 9')
    expect(wrapper.text()).not.toContain('Interno')
  })

  it('muestra campos operativos del contrato real a colaboradores', async () => {
    socket.readyState = 3
    chatApi.sendChat.mockResolvedValue({
      data: { text: 'Resultado', type: 'product_answer', data: { results: [{ name: 'Maceta', formatted_price: '$ 250', stock_status: 'low', sku: 'MAC-1', stock_qty: 3, supplier_name: 'Proveedor A' }] } },
      correlationId: 'cid-staff',
    })
    const wrapper = mountChat('colaborador')
    await flushPromises()
    await wrapper.get('textarea').setValue('precio de maceta')
    await wrapper.get('[aria-label="Enviar"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('MAC-1')
    expect(wrapper.text()).toContain('Stock 3')
    expect(wrapper.text()).toContain('Proveedor A')
  })

  it('libera el envío y avisa si WebSocket se corta durante la respuesta', async () => {
    const wrapper = mountChat()
    await flushPromises()
    await wrapper.get('textarea').setValue('consulta en curso')
    await wrapper.get('[aria-label="Enviar"]').trigger('click')
    socket.onclose?.()
    await flushPromises()

    expect(wrapper.text()).toContain('La conexión se interrumpió')
    expect(wrapper.find('[aria-label="Cancelar"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="Enviar"]').exists()).toBe(true)
  })
})
