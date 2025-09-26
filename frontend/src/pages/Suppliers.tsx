// NG-HEADER: Nombre de archivo: Suppliers.tsx
// NG-HEADER: Ubicación: frontend/src/pages/Suppliers.tsx
// NG-HEADER: Descripción: Listado y gestión de proveedores.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import AppToolbar from '../components/AppToolbar'
import { Supplier, listSuppliers, createSupplier, bulkDeleteSuppliers, BulkDeleteSuppliersResponse } from '../services/suppliers'
import { Link, useNavigate } from 'react-router-dom'
import { PATHS } from '../routes/paths'
import { useTheme } from '../theme/ThemeProvider'

export default function SuppliersPage() {
  const [items, setItems] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ slug: '', name: '', location: '', contact_name: '', contact_email: '', contact_phone: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<number[]>([])
  const [deleting, setDeleting] = useState(false)
  const [resultMsg, setResultMsg] = useState<string | null>(null)
  const [showResult, setShowResult] = useState(false)
  const [resultData, setResultData] = useState<BulkDeleteSuppliersResponse | null>(null)
  const navigate = useNavigate()
  const theme = useTheme()
  useEffect(() => {
    (async () => {
      try { setItems(await listSuppliers()) } finally { setLoading(false) }
    })()
  }, [])

  return (
    <>
      <AppToolbar />
      <div className="panel p-4" style={{ maxWidth: 1000, margin: '16px auto' }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ color: 'var(--muted)', fontSize: 12 }}>Inicio › Proveedores</div>
            <h2 className="fs-xl fw-600" style={{ margin: 0, marginTop: 6 }}>Proveedores</h2>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <button className="btn-primary" onClick={() => setShowCreate(true)}>Nuevo proveedor</button>
            <Link to={PATHS.home} className="btn" style={{ textDecoration: 'none' }}>Volver al inicio</Link>
            <button className="btn" onClick={() => navigate(-1)}>Volver</button>
          </div>
        </div>
        {loading ? (
          <div>Cargando...</div>
        ) : (
          <table className="table w-full table-fixed table-accent-hover">
            <thead>
              <tr>
                <th style={{ width: 36, textAlign: 'center' }}>
                  <input
                    type="checkbox"
                    aria-label="Seleccionar todos"
                    checked={selected.length > 0 && selected.length === items.length}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelected(items.map(i => i.id))
                      } else {
                        setSelected([])
                      }
                    }}
                  />
                </th>
                <th style={{ width: 70, textAlign: 'left' }}>ID</th>
                <th style={{ textAlign: 'left' }}>Nombre</th>
                <th style={{ width: 180, textAlign: 'left' }}>Slug</th>
                <th style={{ width: 160, textAlign: 'left' }}>Ubicación</th>
                <th style={{ width: 140, textAlign: 'left' }}>Contacto</th>
                <th style={{ width: 100, textAlign: 'center' }}>Archivos</th>
              </tr>
            </thead>
            <tbody>
              {items.map(s => (
                <tr key={s.id} style={{ cursor: 'pointer', borderTop: `1px solid ${theme.border}` }}>
                  <td style={{ textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected.includes(s.id)}
                      onChange={(e) => {
                        setSelected(prev => e.target.checked ? [...prev, s.id] : prev.filter(id => id !== s.id))
                      }}
                    />
                  </td>
                  <td onClick={() => navigate(`/proveedores/${s.id}`)}>{s.id}</td>
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
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
          <div className="row" style={{ gap: 8 }}>
            <button
              className="btn-secondary"
              onClick={() => {
                const allIds = items.map(i => i.id)
                const selSet = new Set(selected)
                const inverted = allIds.filter(id => !selSet.has(id))
                setSelected(inverted)
              }}
            >Invertir selección</button>
            <button
              className="btn-danger"
              disabled={selected.length === 0 || deleting}
              onClick={async () => {
                if (selected.length === 0) return
                const confirmText = selected.length === items.length ?
                  `Vas a eliminar ${selected.length} proveedores. ¿Confirmás?` :
                  `Eliminar ${selected.length} proveedores seleccionados. ¿Confirmás?`
                if (!window.confirm(confirmText)) return
                setDeleting(true); setResultMsg(null)
                try {
                  const res: BulkDeleteSuppliersResponse = await bulkDeleteSuppliers(selected)
                  // Filtrar items eliminados
                  const deletedSet = new Set(res.deleted)
                  setItems(prev => prev.filter(it => !deletedSet.has(it.id)))
                  setSelected([])
                  setResultData(res)
                  setShowResult(true)
                } catch (e: any) {
                  setResultMsg(e.message || 'Error eliminando')
                } finally {
                  setDeleting(false)
                }
              }}
            >{deleting ? 'Eliminando...' : `Eliminar seleccionados (${selected.length})`}</button>
          </div>
          <Link to={PATHS.home} className="btn-dark btn-lg" style={{ textDecoration: 'none' }}>Volver</Link>
        </div>
        {resultMsg && (
          <div className="alert" style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>{resultMsg}</div>
        )}
        {showResult && resultData && (
          <div className="modal-backdrop" onClick={() => setShowResult(false)}>
            <div className="modal panel" onClick={e => e.stopPropagation()} style={{ maxWidth: 720, width: '96%', background: theme.card, color: theme.text, border: `1px solid ${theme.border}` }}>
              <h3>Resultado de eliminación</h3>
              <p style={{ marginTop: 0 }}>Solicitados: {resultData.requested.length} · Eliminados: {resultData.deleted.length} · Bloqueados: {resultData.blocked.length} · No encontrados: {resultData.not_found.length}</p>
              {resultData.blocked.length > 0 ? (
                <div style={{ overflowX: 'auto', maxHeight: 360 }}>
                  <table className="table w-full table-fixed table-accent-hover">
                    <thead>
                      <tr>
                        <th style={{ width: 80, textAlign: 'left' }}>ID</th>
                        <th style={{ textAlign: 'left' }}>Motivos</th>
                        <th style={{ width: 120, textAlign: 'right' }}>Compras</th>
                        <th style={{ width: 120, textAlign: 'right' }}>Archivos</th>
                        <th style={{ width: 150, textAlign: 'right' }}>Líneas compra</th>
                      </tr>
                    </thead>
                    <tbody>
                      {resultData.blocked.map(b => (
                        <tr key={b.id}>
                          <td>{b.id}</td>
                          <td>{b.reasons.join(', ')}</td>
                          <td style={{ textAlign: 'right' }}>{b.counts?.purchases ?? 0}</td>
                          <td style={{ textAlign: 'right' }}>{b.counts?.files ?? 0}</td>
                          <td style={{ textAlign: 'right' }}>{b.counts?.purchase_lines ?? 0}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="alert-success">Todos los proveedores seleccionados fueron eliminados.</div>
              )}
              <div className="row" style={{ justifyContent: 'flex-end', marginTop: 12 }}>
                <button className="btn-primary" onClick={() => setShowResult(false)}>Cerrar</button>
              </div>
            </div>
          </div>
        )}
        <div className="row" style={{ justifyContent: 'center', marginTop: 12 }}>
          <Link to={PATHS.home} className="btn-dark btn-lg w-100" style={{ textDecoration: 'none' }}>Volver al inicio</Link>
        </div>
        {showCreate && (
          <div className="modal-backdrop">
            <div className="modal panel" style={{ maxWidth: 520, background: theme.card, color: theme.text, border: `1px solid ${theme.border}` }}>
              <h3>Nuevo proveedor</h3>
              {error && <div className="alert-error">{error}</div>}
              <div className="form-grid" style={{ display: 'grid', gap: 8 }}>
                <label>Slug
                  <input value={form.slug} onChange={e => setForm(f => ({ ...f, slug: e.target.value }))} placeholder="santaplanta" style={{ background: theme.name === 'dark' ? '#111' : '#fff', color: theme.text, border: `1px solid ${theme.border}`, borderRadius: 6, padding: '6px 8px' }} />
                </label>
                <label>Nombre
                  <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Santa Planta" style={{ background: theme.name === 'dark' ? '#111' : '#fff', color: theme.text, border: `1px solid ${theme.border}`, borderRadius: 6, padding: '6px 8px' }} />
                </label>
                <label>Ubicación
                  <input value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} style={{ background: theme.name === 'dark' ? '#111' : '#fff', color: theme.text, border: `1px solid ${theme.border}`, borderRadius: 6, padding: '6px 8px' }} />
                </label>
                <label>Contacto nombre
                  <input value={form.contact_name} onChange={e => setForm(f => ({ ...f, contact_name: e.target.value }))} style={{ background: theme.name === 'dark' ? '#111' : '#fff', color: theme.text, border: `1px solid ${theme.border}`, borderRadius: 6, padding: '6px 8px' }} />
                </label>
                <label>Contacto email
                  <input value={form.contact_email} onChange={e => setForm(f => ({ ...f, contact_email: e.target.value }))} style={{ background: theme.name === 'dark' ? '#111' : '#fff', color: theme.text, border: `1px solid ${theme.border}`, borderRadius: 6, padding: '6px 8px' }} />
                </label>
                <label>Contacto teléfono
                  <input value={form.contact_phone} onChange={e => setForm(f => ({ ...f, contact_phone: e.target.value }))} style={{ background: theme.name === 'dark' ? '#111' : '#fff', color: theme.text, border: `1px solid ${theme.border}`, borderRadius: 6, padding: '6px 8px' }} />
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
