// NG-HEADER: Nombre de archivo: TelegramIdentityPanel.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/chat/components/TelegramIdentityPanel.spec.ts
// NG-HEADER: Descripción: Pruebas de flags, enmascarado y doble aprobación Telegram.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { vuetify } from '../../../app/providers/vuetify'
import { useAuthStore } from '../../../auth/store'

const api = vi.hoisted(() => ({
  getTelegramLinkingStatus: vi.fn(),
  listMyExternalIdentities: vi.fn(),
  createTelegramLinkRequest: vi.fn(),
  revokeMyExternalIdentity: vi.fn(),
  listAdminExternalIdentities: vi.fn(),
  approveExternalIdentity: vi.fn(),
  revokeAdminExternalIdentity: vi.fn(),
}))
vi.mock('../api/externalIdentities', () => api)

import TelegramIdentityPanel from './TelegramIdentityPanel.vue'

function mountPanel(role: 'cliente' | 'admin', userId = 10) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.isAuthenticated = true
  auth.role = role
  auth.user = { id: userId, identifier: `user-${userId}`, role }
  return mount(TelegramIdentityPanel, { global: { plugins: [pinia, vuetify] } })
}

describe('TelegramIdentityPanel', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    api.getTelegramLinkingStatus.mockResolvedValue({ enabled: false, public_bot_enabled: false, transport: 'polling', admin_second_approval: true })
    api.listMyExternalIdentities.mockResolvedValue([])
    api.listAdminExternalIdentities.mockResolvedValue([])
    api.approveExternalIdentity.mockResolvedValue({ status: 'active' })
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('muestra la capacidad preparada sin permitir generar códigos con el flag apagado', async () => {
    const wrapper = mountPanel('cliente')
    await flushPromises()

    expect(wrapper.text()).toContain('permanece deshabilitada por seguridad')
    const button = wrapper.findAll('button').find((item) => item.text().includes('Vincular Telegram'))
    expect(button?.attributes('disabled')).toBeDefined()
  })

  it('impide autoaprobar y permite aprobar la identidad de otro admin', async () => {
    api.listAdminExternalIdentities.mockResolvedValue([
      { id: 1, provider: 'telegram', masked_identifier: 'tg:••••self', user_id: 10, status: 'pending_approval' },
      { id: 2, provider: 'telegram', masked_identifier: 'tg:••••other', user_id: 11, status: 'pending_approval' },
    ])
    const wrapper = mountPanel('admin', 10)
    await flushPromises()

    const approveButtons = wrapper.findAll('button').filter((item) => item.text().includes('Aprobar'))
    expect(approveButtons).toHaveLength(2)
    expect(approveButtons[0].attributes('disabled')).toBeDefined()
    await approveButtons[1].trigger('click')
    await flushPromises()
    expect(api.approveExternalIdentity).toHaveBeenCalledWith(2)
  })
})
