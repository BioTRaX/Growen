// NG-HEADER: Nombre de archivo: KnowledgeCenterDialog.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/knowledge/components/KnowledgeCenterDialog.spec.ts
// NG-HEADER: Descripción: Verifica el modo embebido del Centro de Conocimiento sin overlay.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { vuetify } from '../../../app/providers/vuetify'
import KnowledgeCenterDialog from './KnowledgeCenterDialog.vue'
import {
  getKnowledge,
  getKnowledgeCapabilities,
  getKnowledgeFacts,
  getKnowledgeHistory,
  getKnowledgeJobs,
} from '../api/knowledge'

vi.mock('../api/knowledge', () => ({
  archiveKnowledge: vi.fn(),
  createKnowledge: vi.fn(),
  getKnowledge: vi.fn(),
  getKnowledgeCapabilities: vi.fn(),
  getKnowledgeFacts: vi.fn(),
  getKnowledgeHistory: vi.fn(),
  getKnowledgeJobs: vi.fn(),
  processKnowledge: vi.fn(),
  restoreKnowledge: vi.fn(),
  updateKnowledge: vi.fn(),
  uploadKnowledge: vi.fn(),
}))

describe('KnowledgeCenterDialog', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    vi.mocked(getKnowledge).mockResolvedValue({
      canonical_product_id: 9,
      summary: {
        total: 0,
        confirmed: 0,
        pending: 0,
        archived: 0,
        by_type: { web: 0, document: 0, image: 0, video: 0 },
      },
      items: [],
    })
    vi.mocked(getKnowledgeCapabilities).mockResolvedValue([])
    vi.mocked(getKnowledgeFacts).mockResolvedValue([])
    vi.mocked(getKnowledgeHistory).mockResolvedValue([])
    vi.mocked(getKnowledgeJobs).mockResolvedValue([])
  })

  it('carga como contenido de página sin crear el diálogo principal', async () => {
    const wrapper = mount(KnowledgeCenterDialog, {
      props: { canonicalProductId: 9, embedded: true },
      global: { plugins: [vuetify] },
    })
    await flushPromises()

    expect(getKnowledge).toHaveBeenCalledWith(9, true)
    expect(wrapper.find('.knowledge-center-page').exists()).toBe(true)
    expect(wrapper.find('.knowledge-page-card').exists()).toBe(true)
    expect(wrapper.find('.knowledge-center-dialog').exists()).toBe(false)
    expect(wrapper.text()).toContain('Conocimiento del producto')
    expect(wrapper.text()).toContain('0 activos')
  })
})
