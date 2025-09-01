// NG-HEADER: Nombre de archivo: Stock.tsx
// NG-HEADER: Ubicación: frontend/src/pages/Stock.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import { listSuppliers, Supplier } from '../services/suppliers'
import { useNavigate } from 'react-router-dom'
import { PATHS } from '../routes/paths'
import { listCategories, Category } from '../services/categories'
import { searchProducts, ProductItem, updateStock } from '../services/products'
import { pushTNBulk } from '../services/images'

export default function Stock() {
  const navigate = useNavigate()
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [supplierId, setSupplierId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [q, setQ] = useState('')
  const [items, setItems] = useState<ProductItem[]>([])
  const [page, setPage] = useState(1)
  const [pageSize] = useState(50)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState<number | null>(null)
  const [stockVal, setStockVal] = useState('')
  const [tab, setTab] = useState<'gt' | 'eq'>('gt')
  const [pushing, setPushing] = useState(false)

  useEffect(() => {
    listSuppliers().then(setSuppliers).catch(() => {})
    listCategories().then(setCategories).catch(() => {})
  }, [])

  useEffect(() => {
    const t = setTimeout(() => {
      setLoading(true)
      searchProducts({
        q,
        supplier_id: supplierId ? Number(supplierId) : undefined,
        category_id: categoryId ? Number(categoryId) : undefined,
        page,
        page_size: pageSize,
        stock: tab === 'gt' ? 'gt:0' : 'eq:0',
      })
        .then((r) => {
          setItems(page === 1 ? r.items : [...items, ...r.items])
          setTotal(r.total)
        })
        .finally(() => setLoading(false))
    }, 300)
    return () => clearTimeout(t)
  }, [q, supplierId, categoryId, page, tab])

  function resetAndSearch() {
    setPage(1)
    setItems([])
  }

  async function saveStock(id: number) {
    const num = Number(stockVal)
    if (isNaN(num)) return
    const r = await updateStock(id, num)
    setItems((prev) => prev.map((it) => (it.product_id === id ? { ...it, stock: r.stock } : it)))
    setEditing(null)
  }

  return (
    <div className="panel p-4" style={{ margin: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
  <h2 style={{ marginTop: 0, marginBottom: 8, flex: 1 }}>Stock</h2>
  <div style={{ display: 'flex', gap: 8 }}>
  <button className="btn-dark btn-lg" onClick={() => navigate(PATHS.purchases)}>Compras</button>
    <button className="btn" disabled={pushing || !items.length} onClick={async () => { setPushing(true); try { await pushTNBulk(items.map((i) => i.product_id)); alert('Push Tiendanube (stub) completado'); } finally { setPushing(false) } }}>Enviar imágenes a Tiendanube</button>
  <button className="btn-dark btn-lg" onClick={() => navigate(PATHS.home)}>Volver</button>
  </div>
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <button className={"btn" + (tab === 'gt' ? ' btn-dark' : '')} onClick={() => { setTab('gt'); resetAndSearch() }}>Con stock</button>
        <button className={"btn" + (tab === 'eq' ? ' btn-dark' : '')} onClick={() => { setTab('eq'); resetAndSearch() }}>Sin stock</button>
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <input
          className="input w-full"
          placeholder="Buscar producto..."
          value={q}
          onChange={(e) => { setQ(e.target.value); resetAndSearch() }}
        />
        <select className="select" value={supplierId} onChange={(e) => { setSupplierId(e.target.value); resetAndSearch() }}>
          <option value="">Proveedor</option>
          {suppliers.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        <select className="select" value={categoryId} onChange={(e) => { setCategoryId(e.target.value); resetAndSearch() }}>
          <option value="">Categoría</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>
      <div style={{ fontSize: 12, marginBottom: 8 }}>{total} resultados</div>
  <table className="table w-full">
        <thead>
          <tr>
    <th style={{ textAlign: 'left' }}>Producto</th>
    <th style={{ textAlign: 'left' }}>Proveedor</th>
    <th className="text-center">Precio venta</th>
    <th className="text-center">Compra</th>
    <th className="text-center">Stock</th>
    <th className="text-center">Categoría</th>
    <th className="text-center">Actualizado</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr key={it.product_id}>
      <td style={{ textAlign: 'left' }}>
        <a className="link" href={`/productos/${it.product_id}`}>{it.name}</a>
      </td>
      <td style={{ textAlign: 'left' }}>{it.supplier.name}</td>
      <td className="text-center">{it.precio_venta ?? ''}</td>
      <td className="text-center">{it.precio_compra ?? ''}</td>
      <td className="text-center">
                {editing === it.product_id ? (
                  <span>
                    <input
                      type="number"
                      value={stockVal}
                      onChange={(e) => setStockVal(e.target.value)}
                      style={{ width: 80 }}
                    />
        <button className="btn-primary btn-lg" onClick={() => saveStock(it.product_id)}>Guardar</button>
                  </span>
                ) : (
                  <span>
                    {it.stock}
        <button className="btn-secondary" style={{ marginLeft: 6 }} onClick={() => { setEditing(it.product_id); setStockVal(String(it.stock)) }}>Editar</button>
                  </span>
                )}
              </td>
      <td className="text-center">{it.category_path}</td>
      <td className="text-center">{it.updated_at ? new Date(it.updated_at).toLocaleString() : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <button className="btn-dark btn-lg" disabled={page === 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>Anterior</button>
        <button className="btn-dark btn-lg" disabled={items.length >= total || loading} onClick={() => setPage((p) => p + 1)}>Más</button>
      </div>
    </div>
  )
}
