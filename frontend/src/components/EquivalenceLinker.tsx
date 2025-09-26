// NG-HEADER: Nombre de archivo: EquivalenceLinker.tsx
// NG-HEADER: Ubicación: frontend/src/components/EquivalenceLinker.tsx
// NG-HEADER: Descripción: UI que vincula productos equivalentes.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useState } from 'react'
import { upsertEquivalence } from '../services/equivalences'
import { showToast } from './Toast'
import { baseURL as base } from '../services/http'

interface Props {
  supplierId: number
  supplierProductId: number
  onClose: () => void
}

export default function EquivalenceLinker({
  supplierId,
  supplierProductId,
  onClose,
}: Props) {
  const [canonicalId, setCanonicalId] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    let id: number | null = null
    const raw = canonicalId.trim().toUpperCase()
    // Permitir: número, NG-######, o número directo
    if (/^\d+$/.test(raw)) {
      id = Number(raw)
    } else {
      try {
        const res = await fetch(`${base}/canonical-products/resolve?sku=${encodeURIComponent(raw)}`, { credentials: 'include' })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const j = await res.json()
        id = Number(j?.id)
        if (!id) throw new Error('SKU no resuelto')
      } catch (e: any) {
        showToast('error', 'No se pudo resolver el SKU. Ingresá el ID numérico o un SKU válido (NG-###### o XXX_####_YYY).')
        return
      }
    }
    try {
      setSaving(true)
      await upsertEquivalence({
        supplier_id: supplierId,
        supplier_product_id: supplierProductId,
        canonical_product_id: id,
      })
      showToast('success', 'Equivalencia creada')
      onClose()
    } catch (e: any) {
      showToast('error', e?.message || 'No se pudo crear la equivalencia')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0,0,0,0.3)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div className="panel p-4" style={{ width: 320 }}>
        <h3>Vincular equivalencia</h3>
        <input
          className="input w-full"
          placeholder="ID canónico"
          value={canonicalId}
          onChange={(e) => setCanonicalId(e.target.value)}
        />
        <div style={{ marginTop: 12, textAlign: 'right' }}>
          <button onClick={onClose} style={{ marginRight: 8 }}>
            Cancelar
          </button>
          <button onClick={save} disabled={saving || !canonicalId}>
            {saving ? 'Guardando...' : 'Guardar'}
          </button>
        </div>
      </div>
    </div>
  )
}
