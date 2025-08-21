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

  async function refresh() {
    const r = await http.get<User[]>('/auth/users')
    setUsers(r.data)
  }

  useEffect(() => {
    refresh()
    listSuppliers().then(setSuppliers).catch(() => {})
  }, [])

  const updateUser = async (id: number, data: any) => {
    await http.patch(`/auth/users/${id}`, data)
    refresh()
  }

  const resetPassword = async (id: number) => {
    const r = await http.post(`/auth/users/${id}/reset-password`)
    alert(`Token de reseteo: ${r.data.token}`)
  }

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

      <table className="w-full" style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th>Id</th>
            <th>Identificador</th>
            <th>Email</th>
            <th>Rol</th>
            <th>Proveedor</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.id}</td>
              <td>{u.identifier}</td>
              <td>{u.email}</td>
              <td>
                <select
                  className="select"
                  value={u.role}
                  onChange={(e) => updateUser(u.id, { role: e.target.value })}
                >
                  <option value="cliente">cliente</option>
                  <option value="proveedor">proveedor</option>
                  <option value="colaborador">colaborador</option>
                  <option value="admin">admin</option>
                </select>
              </td>
              <td>
                <select
                  className="select"
                  value={u.supplier_id ?? ''}
                  onChange={(e) =>
                    updateUser(u.id, {
                      supplier_id: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                >
                  <option value="">(ninguno)</option>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </td>
              <td>
                <button className="btn" onClick={() => resetPassword(u.id)}>
                  Resetear contraseña
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
