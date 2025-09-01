// NG-HEADER: Nombre de archivo: EquivalenceLinker.tsx
// NG-HEADER: Ubicación: frontend/src/components/EquivalenceLinker.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useState } from 'react'
import { upsertEquivalence } from '../services/equivalences'

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
    const id = Number(canonicalId)
    if (!id) return
    try {
      setSaving(true)
      await upsertEquivalence({
        supplier_id: supplierId,
        supplier_product_id: supplierProductId,
        canonical_product_id: id,
      })
      onClose()
    } catch (e: any) {
      alert(e.message)
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
