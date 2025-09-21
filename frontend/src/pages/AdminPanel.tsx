// NG-HEADER: Nombre de archivo: AdminPanel.tsx
// NG-HEADER: Ubicación: frontend/src/pages/AdminPanel.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState, lazy, Suspense } from 'react'
import { useNavigate } from 'react-router-dom'
import { PATHS } from '../routes/paths'
import http from '../services/http'
import SupplierAutocomplete from '../components/supplier/SupplierAutocomplete'
import type { SupplierSearchItem } from '../services/suppliers'
const HealthPanel = lazy(() => import('../components/HealthPanel'))
const ServicesPanel = lazy(() => import('../components/ServicesPanel'))

interface User {
  id: number
  identifier: string
  email?: string | null
  name?: string | null
  role: string
  supplier_id?: number | null
}

export default function AdminPanel() {
  const nav = useNavigate()
  const [tab, setTab] = useState<'servicios' | 'usuarios' | 'imagenes'>('servicios')
  const [users, setUsers] = useState<User[]>([])
  const [supplierSel, setSupplierSel] = useState<SupplierSearchItem | null>(null)
  const [form, setForm] = useState({
    identifier: '',
    email: '',
    name: '',
    password: '',
    role: 'cliente',
    supplier_id: '',
  })
  const [edit, setEdit] = useState<User | null>(null)
  const [editForm, setEditForm] = useState({
    email: '',
    name: '',
    role: '',
    supplier_id: '',
  })
  const [editSupplierSel, setEditSupplierSel] = useState<SupplierSearchItem | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [job, setJob] = useState<any | null>(null)
  const [jobForm, setJobForm] = useState({ active: false, mode: 'off', retries: 3, rate_rps: 1, burst: 3, log_retention_days: 90, purge_ttl_days: 30 })
  const [review, setReview] = useState<any[]>([])

  async function refresh() {
    const r = await http.get<User[]>('/auth/users')
    setUsers(r.data)
  }

  useEffect(() => {
    refresh()
    http.get('/admin/image-jobs/status').then((r) => { setJob(r.data); setJobForm({
      active: r.data.active,
      mode: r.data.mode,
      retries: 3,
      rate_rps: 1,
      burst: 3,
      log_retention_days: 90,
      purge_ttl_days: 30,
    }) }).catch(() => {})
    http.get('/products/images/review?status=pending').then(r => setReview(r.data)).catch(() => {})
  }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr(null)
    setCreating(true)
    try {
      await http.post('/auth/users', {
        identifier: form.identifier,
        email: form.email || undefined,
        name: form.name || undefined,
        password: form.password,
        role: form.role,
        supplier_id: form.supplier_id ? Number(form.supplier_id) : undefined,
      })
      setForm({ identifier: '', email: '', name: '', password: '', role: 'cliente', supplier_id: '' })
      refresh()
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'No se pudo crear el usuario'
      setErr(msg)
    } finally {
      setCreating(false)
    }
  }

  const startEdit = (u: User) => {
    setEdit(u)
    setEditForm({
      email: u.email ?? '',
      name: u.name ?? '',
      role: u.role,
      supplier_id: u.supplier_id?.toString() ?? '',
    })
    setEditSupplierSel(u.supplier_id ? { id: u.supplier_id, name: String(u.supplier_id), slug: String(u.supplier_id) } : null)
  }

  const submitEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!edit) return
    await http.patch(`/auth/users/${edit.id}`, {
      email: editForm.email || undefined,
      name: editForm.name || undefined,
      role: editForm.role || undefined,
      supplier_id: editForm.supplier_id ? Number(editForm.supplier_id) : undefined,
    })
    setEdit(null)
    refresh()
  }

  const resetPassword = async (id: number) => {
    const r = await http.post<{ password: string }>(`/auth/users/${id}/reset-password`)
    alert(`Nueva contraseña: ${r.data.password}`)
  }

  const clearLogs = async () => {
    try {
      const r = await http.post<{ status: string; results: string[]; migrations_cleared: number }>(`/debug/clear-logs`)
      const msg = [
        ...r.data.results.slice(0, 5),
        r.data.results.length > 5 ? `... (${r.data.results.length - 5} más)` : undefined,
        `migraciones limpiadas: ${r.data.migrations_cleared}`,
      ].filter(Boolean).join('\n')
      alert(`Logs: ${r.data.status}\n${msg}`)
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'No se pudo limpiar logs (verifica rol/CSRF)'
      alert(msg)
    }
  }

  return (
    <div className="panel p-4" style={{ color: 'var(--text-color)' }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Control Panel</h2>
        <div className="row">
          <button className="btn-dark btn-lg" type="button" onClick={clearLogs}>
            Limpiar logs
          </button>
          <button className="btn-secondary" type="button" onClick={() => (nav ? nav(PATHS.home) : null)}>
            Volver
          </button>
        </div>
      </div>

  {/* Tabs */}
  <div className="row" style={{ gap: 8, marginTop: 12, marginBottom: 12 }}>
    <button className={"btn"} onClick={() => setTab('servicios')} style={{ borderColor: tab==='servicios' ? 'var(--primary)' : undefined, color: tab==='servicios' ? 'var(--primary)' : undefined }}>Servicios</button>
    <button className={"btn"} onClick={() => setTab('usuarios')} style={{ borderColor: tab==='usuarios' ? 'var(--primary)' : undefined, color: tab==='usuarios' ? 'var(--primary)' : undefined }}>Usuarios</button>
    <button className={"btn"} onClick={() => setTab('imagenes')} style={{ borderColor: tab==='imagenes' ? 'var(--primary)' : undefined, color: tab==='imagenes' ? 'var(--primary)' : undefined }}>Imágenes</button>
  </div>

  {tab === 'servicios' && (
    <div className="card" style={{ padding: 12, marginBottom: 16 }}>
      <h3>Servicios y Health</h3>
      <div style={{ marginBottom: 8 }}>
        <Suspense fallback={<div>Cargando...</div>}>
          <HealthPanel />
        </Suspense>
      </div>
      <Suspense fallback={<div>Cargando...</div>}>
        <ServicesPanel />
      </Suspense>
    </div>
  )}

  {tab === 'usuarios' && (
    <>
      <form onSubmit={submit} className="flex flex-col gap-2 mb-4">
        <input
          className="input"
          value={form.identifier}
          onChange={(e) => setForm({ ...form, identifier: e.target.value })}
          placeholder="Identificador"
          required
        />
        <input
          className="input"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          placeholder="Email"
        />
        <input
          className="input"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="Nombre"
        />
        <input
          className="input"
          type="password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          placeholder="Contraseña"
          required
        />
        <select
          className="select"
          value={form.role}
          onChange={(e) => setForm({ ...form, role: e.target.value })}
        >
          <option value="cliente">cliente</option>
          <option value="proveedor">proveedor</option>
          <option value="colaborador">colaborador</option>
          <option value="admin">admin</option>
        </select>
        <SupplierAutocomplete
          value={supplierSel}
          onChange={(item) => { setSupplierSel(item); setForm({ ...form, supplier_id: item ? String(item.id) : '' }) }}
          placeholder="Proveedor (opcional)"
        />
        <button className="btn-primary" type="submit" disabled={creating}>
          {creating ? 'Creando...' : 'Crear usuario'}
        </button>
        {err && <div style={{color:'#fca5a5'}}>{err}</div>}
      </form>

      {edit && (
        <form onSubmit={submitEdit} className="flex flex-col gap-2 mb-4">
          <h3>Editar {edit.identifier}</h3>
          <input
            className="input"
            value={editForm.email}
            onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
            placeholder="Email"
          />
          <input
            className="input"
            value={editForm.name}
            onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
            placeholder="Nombre"
          />
          <select
            className="select"
            value={editForm.role}
            onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
          >
            <option value="cliente">cliente</option>
            <option value="proveedor">proveedor</option>
            <option value="colaborador">colaborador</option>
            <option value="admin">admin</option>
          </select>
          <SupplierAutocomplete
            value={editSupplierSel}
            onChange={(item) => { setEditSupplierSel(item); setEditForm({ ...editForm, supplier_id: item ? String(item.id) : '' }) }}
            placeholder="Proveedor (opcional)"
          />
          <button className="btn-primary" type="submit">
            Guardar cambios
          </button>
          <button className="btn-secondary" type="button" onClick={() => setEdit(null)}>
            Cancelar
          </button>
        </form>
      )}

      <table className="w-full" style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th>Id</th>
            <th>Identificador</th>
            <th>Email</th>
            <th>Rol</th>
            <th>Proveedor</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.id}</td>
              <td>{u.identifier}</td>
              <td>{u.email}</td>
              <td>{u.role}</td>
              <td>{u.supplier_id ?? ''}</td>
              <td className="flex gap-2">
                <button className="btn-secondary" type="button" onClick={() => startEdit(u)}>
                  Editar
                </button>
                <button className="btn-secondary" type="button" onClick={() => resetPassword(u.id)}>
                  Reset
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )}

  {tab === 'imagenes' && (
    <>
      <div className="card" style={{ padding: 12, marginBottom: 16 }}>
        <h3>Job: Imágenes productos</h3>
        {job && (
          <div style={{ fontSize: 14, marginBottom: 8 }}>
            <div>Activo: {job.active ? 'Sí' : 'No'} | Modo: {job.mode} | Ejecutando: {job.running ? 'Sí' : 'No'} | Pendientes: {job.pending}</div>
          </div>
        )}
        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
          <label>Activo <input type="checkbox" checked={jobForm.active} onChange={(e) => setJobForm({ ...jobForm, active: e.target.checked })} /></label>
          <select className="select" value={jobForm.mode} onChange={(e) => setJobForm({ ...jobForm, mode: e.target.value })}>
            <option value="off">Off</option>
            <option value="on">On</option>
            <option value="window">Ventana</option>
          </select>
          <input className="input" type="number" value={jobForm.retries} onChange={(e) => setJobForm({ ...jobForm, retries: Number(e.target.value) })} placeholder="Reintentos" />
          <input className="input" type="number" step="0.1" value={jobForm.rate_rps} onChange={(e) => setJobForm({ ...jobForm, rate_rps: Number(e.target.value) })} placeholder="rate_rps" />
          <input className="input" type="number" value={jobForm.burst} onChange={(e) => setJobForm({ ...jobForm, burst: Number(e.target.value) })} placeholder="burst" />
          <input className="input" type="number" value={jobForm.purge_ttl_days} onChange={(e) => setJobForm({ ...jobForm, purge_ttl_days: Number(e.target.value) })} placeholder="TTL purge" />
          <input className="input" type="number" value={jobForm.log_retention_days} onChange={(e) => setJobForm({ ...jobForm, log_retention_days: Number(e.target.value) })} placeholder="Retencion logs" />
          <button className="btn-dark btn-lg" type="button" onClick={async () => { await http.put('/admin/image-jobs/settings', jobForm); const r = await http.get('/admin/image-jobs/status'); setJob(r.data) }}>Guardar</button>
        </div>
        <div style={{ marginTop: 8 }}>
          <strong>Logs recientes</strong>
          <ul>
            {job?.logs?.map((l: any, i: number) => <li key={i}>[{l.level}] {l.created_at} - {l.message}</li>)}
          </ul>
          <div className="row" style={{ gap: 8 }}>
            <button className="btn" type="button" onClick={async () => { await http.post('/admin/image-jobs/trigger/crawl-missing'); alert('Crawl encolado') }}>Forzar escaneo catálogo</button>
            <button className="btn" type="button" onClick={async () => { await http.post('/admin/image-jobs/trigger/purge'); alert('Purge encolado') }}>Purgar soft-deleted</button>
          </div>
        </div>
      </div>

      {/* Review queue */}
      <div className="card" style={{ padding: 12, marginBottom: 16 }}>
        <h3>Revisión de imágenes pendientes</h3>
        <table className="w-full">
          <thead>
            <tr>
              <th>ID</th>
              <th>Producto</th>
              <th>Imagen</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {review.map((r) => (
              <tr key={r.image_id}>
                <td>{r.image_id}</td>
                <td>{r.product_id}</td>
                <td>{r.path}</td>
                <td className="row" style={{ gap: 6 }}>
                  <button className="btn-secondary" onClick={async () => { await http.post(`/products/images/${r.image_id}/review/approve`, null, { params: { lock: true } }); setReview((prev) => prev.filter((x: any) => x.image_id !== r.image_id)) }}>Aprobar+Lock</button>
                  <button className="btn" onClick={async () => { await http.post(`/products/images/${r.image_id}/review/reject`, { soft_delete: true }); setReview((prev) => prev.filter((x: any) => x.image_id !== r.image_id)) }}>Rechazar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )}
    </div>
  )
}
