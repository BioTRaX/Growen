// NG-HEADER: Nombre de archivo: useMassCanonicalDraft.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/composables/useMassCanonicalDraft.spec.ts
// NG-HEADER: Descripción: Pruebas de recuperación, expiración y migración de borradores canónicos.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  LEGACY_MASS_CANONICAL_KEY,
  isValidMassCanonicalDraft,
  massCanonicalStorageKey,
  migrateLegacyMassCanonical,
  useMassCanonicalDraft,
} from './useMassCanonicalDraft'

describe('useMassCanonicalDraft', () => {
  beforeEach(() => localStorage.clear())

  it('aísla la clave por usuario y persiste un borrador v3', () => {
    const state = useMassCanonicalDraft(42)
    state.create([{
      sourceProductId: 8,
      internalProductId: 3,
      sourceName: 'Producto',
      supplierName: 'Proveedor',
      name: 'Producto',
      brand: '',
      categoryId: null,
      subcategoryId: null,
      tagNames: [],
      previewSku: null,
    }])
    expect(localStorage.getItem(massCanonicalStorageKey(42))).toContain('"version":3')
    expect(localStorage.getItem(massCanonicalStorageKey(7))).toBeNull()
  })

  it('rechaza borradores vencidos', () => {
    expect(isValidMassCanonicalDraft({
      version: 3,
      userId: 1,
      clientRequestId: 'x',
      expiresAt: new Date(0).toISOString(),
      rows: [],
    }, 1)).toBe(false)
  })

  it('convierte la sesión React heredada y elimina la clave sólo al persistir', () => {
    const legacy = {
      sourceProducts: [{ product_id: 21, preferred_name: 'Maceta', supplier_name: 'Proveedor' }],
      processedDrafts: [{ sourceProductId: 21, name: 'Maceta 10L', brand: 'Grow', categoryId: 4, subcategoryId: 5 }],
    }
    expect(migrateLegacyMassCanonical(legacy, 9)?.rows[0].brand).toBe('Grow')
    localStorage.setItem(LEGACY_MASS_CANONICAL_KEY, JSON.stringify(legacy))
    const state = useMassCanonicalDraft(9)
    expect(state.load()?.rows[0].name).toBe('Maceta 10L')
    expect(localStorage.getItem(LEGACY_MASS_CANONICAL_KEY)).toBeNull()
  })

  it('migra un borrador v2 agregando tags vacíos', () => {
    const expiresAt = new Date(Date.now() + 60_000).toISOString()
    localStorage.setItem('growen.products.mass-canonical.v2:5', JSON.stringify({
      version: 2,
      userId: 5,
      clientRequestId: 'v2-request',
      step: 2,
      updatedAt: new Date().toISOString(),
      expiresAt,
      jobId: null,
      rows: [{
        sourceProductId: 1, internalProductId: 1, sourceName: 'A', supplierName: 'S', name: 'A',
        brand: '', categoryId: 2, subcategoryId: 3, previewSku: null,
      }],
    }))
    const migrated = useMassCanonicalDraft(5).load()
    expect(migrated?.version).toBe(3)
    expect(migrated?.commonTagNames).toEqual([])
    expect(migrated?.rows[0].tagNames).toEqual([])
    expect(localStorage.getItem('growen.products.mass-canonical.v2:5')).toBeNull()
  })

  it('guarda cambios reactivos con debounce', async () => {
    vi.useFakeTimers()
    const state = useMassCanonicalDraft(2)
    state.create([{
      sourceProductId: 1, internalProductId: 1, sourceName: 'A', supplierName: 'S', name: 'A', brand: '', categoryId: null, subcategoryId: null, tagNames: [], previewSku: null,
    }])
    state.draft.value!.rows[0].brand = 'Nueva'
    await vi.runAllTimersAsync()
    expect(localStorage.getItem(massCanonicalStorageKey(2))).toContain('Nueva')
    vi.useRealTimers()
  })
})
