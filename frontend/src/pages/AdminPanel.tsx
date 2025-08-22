import { useEffect, useState } from 'react'
import http from '../services/http'
import { listSuppliers, Supplier } from '../services/suppliers'

interface User {
  id: number
  identifier: string
  email?: string | null
  name?: string | null
  role: string
  supplier_id?: number | null
}

export default function AdminPanel() {
  const [users, setUsers] = useState<User[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
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

  async function refresh() {
    const r = await http.get<User[]>('/auth/users')
    setUsers(r.data)
  }

  useEffect(() => {
    refresh()
    listSuppliers().then(setSuppliers).catch(() => {})
  }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
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
  }

  const startEdit = (u: User) => {
    setEdit(u)
    setEditForm({
      email: u.email ?? '',
      name: u.name ?? '',
      role: u.role,
      supplier_id: u.supplier_id?.toString() ?? '',
    })
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
    <div className="panel p-4" style={{ color: 'var(--text-color)' }}>
      <h2>Control Panel</h2>
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
        <select
          className="select"
          value={form.supplier_id}
          onChange={(e) => setForm({ ...form, supplier_id: e.target.value })}
        >
          <option value="">Proveedor (opcional)</option>
          {suppliers.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <button className="btn-primary" type="submit">
          Crear usuario
        </button>
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
          <select
            className="select"
            value={editForm.supplier_id}
            onChange={(e) => setEditForm({ ...editForm, supplier_id: e.target.value })}
          >
            <option value="">Proveedor (opcional)</option>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
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
    </div>
  )
}
