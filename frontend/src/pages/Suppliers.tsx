// NG-HEADER: Nombre de archivo: Suppliers.tsx
// NG-HEADER: Ubicación: frontend/src/pages/Suppliers.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import AppToolbar from '../components/AppToolbar'
import { Supplier, listSuppliers, createSupplier } from '../services/suppliers'
import { Link, useNavigate } from 'react-router-dom'
import { PATHS } from '../routes/paths'

export default function SuppliersPage() {
  const [items, setItems] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ slug: '', name: '', location: '', contact_name: '', contact_email: '', contact_phone: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  useEffect(() => {
    (async () => {
      try { setItems(await listSuppliers()) } finally { setLoading(false) }
    })()
  }, [])

  return (
    <>
      <AppToolbar />
      <div className="panel p-4" style={{ maxWidth: 900, margin: '16px auto' }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <h2>Proveedores</h2>
          <div className="row" style={{ gap: 8 }}>
            <button className="btn-primary" onClick={() => setShowCreate(true)}>Nuevo proveedor</button>
            <Link to={PATHS.home} className="btn-secondary btn-lg" style={{ textDecoration: 'none' }}>Volver</Link>
          </div>
        </div>
        {loading ? (
          <div>Cargando...</div>
        ) : (
          <table className="table w-full table-fixed">
            <thead>
              <tr>
                <th style={{ width: 70 }}>ID</th>
                <th>Nombre</th>
                <th style={{ width: 180 }}>Slug</th>
                <th style={{ width: 160 }}>Ubicación</th>
                <th style={{ width: 140 }}>Contacto</th>
                <th style={{ width: 100 }}>Archivos</th>
              </tr>
            </thead>
            <tbody>
              {items.map(s => (
                <tr key={s.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/proveedores/${s.id}`)}>
                  <td>{s.id}</td>
                  <td>{s.name}</td>
                  <td>{s.slug}</td>
                  <td>{(s as any).location || ''}</td>
                  <td>{(s as any).contact_name || ''}</td>
                  <td style={{ textAlign: 'center' }}>{(s as any).files_count ?? '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="row" style={{ justifyContent: 'center', marginTop: 12 }}>
          <Link to={PATHS.home} className="btn-secondary btn-lg" style={{ textDecoration: 'none' }}>Volver al inicio</Link>
        </div>
        {showCreate && (
          <div className="modal-backdrop">
            <div className="modal panel" style={{ maxWidth: 520 }}>
              <h3>Nuevo proveedor</h3>
              {error && <div className="alert-error">{error}</div>}
              <div className="form-grid" style={{ display: 'grid', gap: 8 }}>
                <label>Slug
                  <input value={form.slug} onChange={e => setForm(f => ({ ...f, slug: e.target.value }))} placeholder="santaplanta" />
                </label>
                <label>Nombre
                  <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Santa Planta" />
                </label>
                <label>Ubicación
                  <input value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} />
                </label>
                <label>Contacto nombre
                  <input value={form.contact_name} onChange={e => setForm(f => ({ ...f, contact_name: e.target.value }))} />
                </label>
                <label>Contacto email
                  <input value={form.contact_email} onChange={e => setForm(f => ({ ...f, contact_email: e.target.value }))} />
                </label>
                <label>Contacto teléfono
                  <input value={form.contact_phone} onChange={e => setForm(f => ({ ...f, contact_phone: e.target.value }))} />
                </label>
              </div>
              <div className="row" style={{ justifyContent: 'flex-end', marginTop: 16, gap: 8 }}>
                <button className="btn-secondary" onClick={() => setShowCreate(false)}>Cancelar</button>
                <button className="btn-primary" disabled={saving || !form.slug || !form.name} onClick={async () => {
                  setSaving(true); setError(null)
                  try {
                    const created = await createSupplier({ ...form })
                    setItems(it => [...it, created])
                    setShowCreate(false)
                    navigate(`/proveedores/${created.id}`)
                  } catch (e: any) {
                    setError(e.message || 'Error al crear')
                  } finally {
                    setSaving(false)
                  }
                }}>{saving ? 'Guardando...' : 'Crear'}</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
