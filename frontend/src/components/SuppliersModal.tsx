import { useEffect, useState } from 'react'
import { listSuppliers, Supplier } from '../services/suppliers'
import CreateSupplierModal from './CreateSupplierModal'

interface Props {
  open: boolean
  onClose: () => void
}

export default function SuppliersModal({ open, onClose }: Props) {
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [error, setError] = useState('')
  const [createOpen, setCreateOpen] = useState(false)

  function refresh() {
    listSuppliers()
      .then(setSuppliers)
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    if (open) refresh()
  }, [open])

  if (!open) return null

  return (
    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: 'var(--panel-bg)', color: 'var(--text-color)', padding: 20, borderRadius: 8, width: 400 }}>
        <h3>Proveedores</h3>
        {error && <div style={{ color: 'var(--text-color)' }}>{error}</div>}
        {suppliers.length === 0 ? (
          <div>No hay proveedores aún</div>
        ) : (
          <ul>
            {suppliers.map((s) => (
              <li key={s.id}>
                {s.name} <small>({s.slug})</small>
              </li>
            ))}
          </ul>
        )}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
          <button onClick={() => setCreateOpen(true)}>Agregar proveedor</button>
          <button onClick={onClose}>Cerrar</button>
        </div>
        {createOpen && (
          <CreateSupplierModal
            open={createOpen}
            onClose={() => setCreateOpen(false)}
            onCreated={(s) => {
              setCreateOpen(false)
              refresh()
            }}
          />
        )}
      </div>
    </div>
  )
}
