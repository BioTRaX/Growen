// NG-HEADER: Nombre de archivo: useMassCanonicalDraft.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/composables/useMassCanonicalDraft.ts
// NG-HEADER: Descripción: Persistencia versionada y migración de borradores de alta masiva canónica.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { ref, watch, type Ref } from 'vue'

import type { MassCanonicalDraft, MassCanonicalDraftRow } from '../types'

type MassCanonicalDraftV2 = Omit<MassCanonicalDraft, 'version' | 'commonTagNames' | 'rows'> & {
  version: 2
  rows: Array<Omit<MassCanonicalDraftRow, 'tagNames'> & { tagNames?: string[] }>
}

export const LEGACY_MASS_CANONICAL_KEY = 'mass_cannon_session'
export const MASS_CANONICAL_TTL_MS = 30 * 24 * 60 * 60 * 1000

export function massCanonicalStorageKey(userId: number): string {
  return `growen.products.mass-canonical.v3:${userId}`
}

function previousStorageKey(userId: number): string {
  return `growen.products.mass-canonical.v2:${userId}`
}

export function newClientRequestId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function isValidMassCanonicalDraft(value: unknown, userId: number, now = Date.now()): value is MassCanonicalDraft {
  if (!value || typeof value !== 'object') return false
  const draft = value as Partial<MassCanonicalDraft>
  return draft.version === 3 && draft.userId === userId && typeof draft.clientRequestId === 'string' &&
    typeof draft.expiresAt === 'string' && Date.parse(draft.expiresAt) > now && Array.isArray(draft.rows)
}

export function migrateLegacyMassCanonical(value: unknown, userId: number): MassCanonicalDraft | null {
  if (!value || typeof value !== 'object') return null
  const legacy = value as { sourceProducts?: Array<Record<string, unknown>>; processedDrafts?: Array<Record<string, unknown>>; currentIndex?: number }
  const sources = Array.isArray(legacy.sourceProducts) ? legacy.sourceProducts : []
  const processed = Array.isArray(legacy.processedDrafts) ? legacy.processedDrafts : []
  if (!sources.length) return null
  const bySource = new Map(processed.map((row) => [Number(row.sourceProductId), row]))
  const rows = sources.map((source): MassCanonicalDraftRow => {
    const sourceProductId = Number(source.product_id ?? source.sourceProductId)
    const prior = bySource.get(sourceProductId)
    return {
      sourceProductId,
      internalProductId: Number(source.internalProductId ?? source.product_id ?? 0),
      sourceName: String(source.preferred_name ?? source.name ?? ''),
      supplierName: String(source.supplier_name ?? source.supplierName ?? ''),
      name: String(prior?.name ?? source.preferred_name ?? source.name ?? ''),
      brand: String(prior?.brand ?? ''),
      categoryId: Number(prior?.categoryId) || null,
      subcategoryId: Number(prior?.subcategoryId) || null,
      tagNames: Array.isArray(prior?.tagNames) ? prior.tagNames.map(String) : [],
      previewSku: null,
    }
  }).filter((row) => Number.isInteger(row.sourceProductId) && row.sourceProductId > 0)
  if (!rows.length) return null
  const now = Date.now()
  return {
    version: 3,
    userId,
    clientRequestId: newClientRequestId(),
    step: 1,
    updatedAt: new Date(now).toISOString(),
    expiresAt: new Date(now + MASS_CANONICAL_TTL_MS).toISOString(),
    jobId: null,
    commonTagNames: [],
    rows,
  }
}

export function useMassCanonicalDraft(userId: number): {
  draft: Ref<MassCanonicalDraft | null>
  recoverable: Ref<boolean>
  load: () => MassCanonicalDraft | null
  create: (rows: MassCanonicalDraftRow[]) => MassCanonicalDraft
  discard: () => void
} {
  const draft = ref<MassCanonicalDraft | null>(null)
  const recoverable = ref(false)
  const key = massCanonicalStorageKey(userId)
  let timer: ReturnType<typeof setTimeout> | undefined

  function persist(): void {
    if (!draft.value) return
    const now = Date.now()
    const saved: MassCanonicalDraft = {
      ...draft.value,
      updatedAt: new Date(now).toISOString(),
      expiresAt: new Date(now + MASS_CANONICAL_TTL_MS).toISOString(),
    }
    localStorage.setItem(key, JSON.stringify(saved))
    recoverable.value = true
  }

  function load(): MassCanonicalDraft | null {
    try {
      const saved = JSON.parse(localStorage.getItem(key) ?? 'null') as unknown
      if (isValidMassCanonicalDraft(saved, userId)) {
        draft.value = saved
        recoverable.value = true
        return saved
      }
      if (saved) localStorage.removeItem(key)
    } catch {
      localStorage.removeItem(key)
    }
    try {
      const previousKey = previousStorageKey(userId)
      const previous = JSON.parse(localStorage.getItem(previousKey) ?? 'null') as Partial<MassCanonicalDraftV2>
      if (previous?.version === 2 && previous.userId === userId && Array.isArray(previous.rows) &&
        typeof previous.expiresAt === 'string' && Date.parse(previous.expiresAt) > Date.now()) {
        const migrated: MassCanonicalDraft = {
          ...(previous as Omit<MassCanonicalDraftV2, 'version' | 'rows'>),
          version: 3,
          commonTagNames: [],
          rows: previous.rows.map((row) => ({ ...row, tagNames: Array.isArray(row.tagNames) ? row.tagNames : [] })),
        }
        draft.value = migrated
        localStorage.setItem(key, JSON.stringify(migrated))
        localStorage.removeItem(previousKey)
        recoverable.value = true
        return migrated
      }
    } catch {
      // El borrador v2 inválido se ignora sin afectar la clave vigente.
    }
    try {
      const legacyRaw = localStorage.getItem(LEGACY_MASS_CANONICAL_KEY)
      const migrated = legacyRaw ? migrateLegacyMassCanonical(JSON.parse(legacyRaw), userId) : null
      if (migrated) {
        draft.value = migrated
        localStorage.setItem(key, JSON.stringify(migrated))
        localStorage.removeItem(LEGACY_MASS_CANONICAL_KEY)
        recoverable.value = true
        return migrated
      }
    } catch {
      // La clave heredada se conserva para permitir un descarte explícito.
    }
    return null
  }

  function create(rows: MassCanonicalDraftRow[]): MassCanonicalDraft {
    const now = Date.now()
    draft.value = {
      version: 3,
      userId,
      clientRequestId: newClientRequestId(),
      step: 1,
      updatedAt: new Date(now).toISOString(),
      expiresAt: new Date(now + MASS_CANONICAL_TTL_MS).toISOString(),
      jobId: null,
      commonTagNames: [],
      rows,
    }
    persist()
    return draft.value
  }

  function discard(): void {
    draft.value = null
    recoverable.value = false
    localStorage.removeItem(key)
    localStorage.removeItem(previousStorageKey(userId))
    localStorage.removeItem(LEGACY_MASS_CANONICAL_KEY)
  }

  watch(draft, () => {
    if (timer) clearTimeout(timer)
    if (draft.value) timer = setTimeout(persist, 300)
  }, { deep: true })

  return { draft, recoverable, load, create, discard }
}
