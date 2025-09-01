// NG-HEADER: Nombre de archivo: Suppliers.tsx
// NG-HEADER: Ubicación: frontend/src/pages/Suppliers.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import AppToolbar from '../components/AppToolbar'
import { Supplier, listSuppliers } from '../services/suppliers'
import { Link } from 'react-router-dom'
import { PATHS } from '../routes/paths'

export default function SuppliersPage() {
  const [items, setItems] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
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
          <Link to={PATHS.home} className="btn-secondary btn-lg" style={{ textDecoration: 'none' }}>Volver</Link>
        </div>
        {loading ? (
          <div>Cargando...</div>
        ) : (
          <table className="table w-full table-fixed">
            <thead>
              <tr>
                <th style={{ width: 100 }}>ID</th>
                <th>Nombre</th>
                <th style={{ width: 220 }}>Slug</th>
              </tr>
            </thead>
            <tbody>
              {items.map(s => (
                <tr key={s.id}>
                  <td>{s.id}</td>
                  <td>{s.name}</td>
                  <td>{s.slug}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="row" style={{ justifyContent: 'center', marginTop: 12 }}>
          <Link to={PATHS.home} className="btn-secondary btn-lg" style={{ textDecoration: 'none' }}>Volver al inicio</Link>
        </div>
      </div>
    </>
  )
}
