import { useEffect, useState } from 'react'
import http from '../../services/http'
import SupplierAutocomplete from '../../components/supplier/SupplierAutocomplete'
import type { SupplierSearchItem } from '../../services/suppliers'

interface User {
  id: number
  identifier: string
  email?: string | null
  name?: string | null
  role: string
  supplier_id?: number | null
}

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([])
  const [supplierSel, setSupplierSel] = useState<SupplierSearchItem | null>(null)
  const [q, setQ] = useState('')
  const [role, setRole] = useState('')
  const [form, setForm] = useState({ identifier: '', email: '', name: '', password: '', role: 'cliente', supplier_id: '' })
  const [edit, setEdit] = useState<User | null>(null)
  const [editForm, setEditForm] = useState({ email: '', name: '', role: '', supplier_id: '' })
  const [editSupplierSel, setEditSupplierSel] = useState<SupplierSearchItem | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  async function refresh() {
    const r = await http.get<User[]>('/auth/users', { params: { q, role: role || undefined } })
    setUsers(r.data)
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, role])

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
  setEditForm({ email: u.email ?? '', name: u.name ?? '', role: u.role, supplier_id: u.supplier_id?.toString() ?? '' })
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

  return (
    <div className="card" style={{ padding: 12 }}>
      <div className="row" style={{ gap: 8, alignItems: 'center', marginBottom: 8 }}>
        <input className="input" placeholder="Buscar nombre/email" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="select" value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="">Rol (todos)</option>
          <option value="cliente">cliente</option>
          <option value="proveedor">proveedor</option>
          <option value="colaborador">colaborador</option>
          <option value="admin">admin</option>
        </select>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-2 mb-4">
        <input className="input" value={form.identifier} onChange={(e) => setForm({ ...form, identifier: e.target.value })} placeholder="Identificador" required />
        <input className="input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="Email" />
        <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Nombre" />
        <input className="input" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="Contraseña" required />
        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
          <select className="select" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
            <option value="cliente">cliente</option>
            <option value="proveedor">proveedor</option>
            <option value="colaborador">colaborador</option>
            <option value="admin">admin</option>
          </select>
          <SupplierAutocomplete value={supplierSel} onChange={(item) => { setSupplierSel(item); setForm({ ...form, supplier_id: item ? String(item.id) : '' }) }} placeholder="Proveedor (opcional)" />
          <button className="btn-primary" type="submit" disabled={creating}>{creating ? 'Creando...' : 'Crear usuario'}</button>
          {err && <div style={{color:'#fca5a5'}}>{err}</div>}
        </div>
      </form>

      {edit && (
        <form onSubmit={submitEdit} className="flex flex-col gap-2 mb-4">
          <h3>Editar {edit.identifier}</h3>
          <input className="input" value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} placeholder="Email" />
          <input className="input" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} placeholder="Nombre" />
          <select className="select" value={editForm.role} onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}>
            <option value="cliente">cliente</option>
            <option value="proveedor">proveedor</option>
            <option value="colaborador">colaborador</option>
            <option value="admin">admin</option>
          </select>
          <SupplierAutocomplete value={editSupplierSel} onChange={(item) => { setEditSupplierSel(item); setEditForm({ ...editForm, supplier_id: item ? String(item.id) : '' }) }} placeholder="Proveedor (opcional)" />
          <div className="row" style={{ gap: 8 }}>
            <button className="btn-primary" type="submit">Guardar cambios</button>
            <button className="btn-secondary" type="button" onClick={() => setEdit(null)}>Cancelar</button>
          </div>
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
                <button className="btn-secondary" type="button" onClick={() => startEdit(u)}>Editar</button>
                <button className="btn-secondary" type="button" onClick={() => resetPassword(u.id)}>Reset</button>
                <button className="btn" type="button" onClick={async () => { if (window.confirm(`Eliminar usuario ${u.identifier}? Esta acción es irreversible.`)) { await http.delete(`/auth/users/${u.id}`); refresh() } }}>Eliminar</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
