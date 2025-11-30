// NG-HEADER: Nombre de archivo: Customers.tsx
// NG-HEADER: Ubicación: frontend/src/pages/Customers.tsx
// NG-HEADER: Descripción: Listado y alta básica de clientes
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppToolbar from '../components/AppToolbar'
import { listCustomers, createCustomer, type Customer } from '../services/customers'

export default function CustomersPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState<Customer[]>([])
  const [loading, setLoading] = useState(false)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')

  async function reload() {
    setLoading(true)
    try {
      const r = await listCustomers({ page_size: 200 })
      setItems(r.items)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { reload() }, [])

  async function onCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    await createCustomer({ name, email })
    setName(''); setEmail('')
    reload()
  }

  return (
    <>
      <AppToolbar />
      <div className="panel" style={{ margin: 16, padding: 12 }}>
        <h2>Clientes</h2>
        <form onSubmit={onCreate} style={{ display:'flex', gap:8, alignItems:'center', marginBottom:12 }}>
          <input placeholder="Nombre" value={name} onChange={e=>setName(e.target.value)} />
          <input placeholder="Email (opcional)" value={email} onChange={e=>setEmail(e.target.value)} />
          <button className="btn-dark" type="submit">Crear</button>
        </form>
        {loading ? <div>Cargando…</div> : (
          <table className="table">
            <thead><tr><th>ID</th><th>Nombre</th><th>Email</th><th>Teléfono</th></tr></thead>
            <tbody>
              {items.map(c => (
                <tr 
                  key={c.id}
                  onClick={() => navigate(`/clientes/${c.id}`)}
                  style={{ cursor: 'pointer' }}
                  className="clickable-row"
                >
                  <td>{c.id}</td>
                  <td>{c.name}</td>
                  <td>{c.email}</td>
                  <td>{c.phone}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
