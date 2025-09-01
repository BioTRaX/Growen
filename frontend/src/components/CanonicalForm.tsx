// NG-HEADER: Nombre de archivo: CanonicalForm.tsx
// NG-HEADER: Ubicación: frontend/src/components/CanonicalForm.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import {
  createCanonicalProduct,
  getCanonicalProduct,
  updateCanonicalProduct,
  CanonicalProduct,
} from '../services/canonical'

interface Props {
  canonicalId?: number
  onClose: () => void
  onSaved?: (cp: CanonicalProduct) => void
}

export default function CanonicalForm({ canonicalId, onClose, onSaved }: Props) {
  const [name, setName] = useState('')
  const [brand, setBrand] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (canonicalId) {
      getCanonicalProduct(canonicalId)
        .then((cp) => {
          setName(cp.name)
          setBrand(cp.brand || '')
        })
        .catch(() => {})
    }
  }, [canonicalId])

  async function save() {
    try {
      setSaving(true)
      let cp: CanonicalProduct
      if (canonicalId) {
        cp = await updateCanonicalProduct(canonicalId, {
          name,
          brand: brand || null,
        })
      } else {
        cp = await createCanonicalProduct({
          name,
          brand: brand || null,
        })
      }
      onSaved?.(cp)
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
      <div className="panel p-4" style={{ width: 400 }}>
        <h3>{canonicalId ? 'Editar canónico' : 'Nuevo canónico'}</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <input
            className="input"
            placeholder="Nombre"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            className="input"
            placeholder="Marca"
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
          />
        </div>
        <div style={{ marginTop: 12, textAlign: 'right' }}>
          <button onClick={onClose} style={{ marginRight: 8 }}>
            Cancelar
          </button>
          <button onClick={save} disabled={saving || !name}>
            {saving ? 'Guardando...' : 'Guardar'}
          </button>
        </div>
      </div>
    </div>
  )
}
