import { useEffect, useState } from 'react'
import { listSuppliers, Supplier } from '../services/suppliers'
import { listCategories, Category } from '../services/categories'
import {
  searchProducts,
  ProductItem,
  updateStock,
} from '../services/products'

interface Props {
  open: boolean
  onClose: () => void
}

export default function ProductsDrawer({ open, onClose }: Props) {
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [supplierId, setSupplierId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [q, setQ] = useState('')
  const [items, setItems] = useState<ProductItem[]>([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [editing, setEditing] = useState<number | null>(null)
  const [stockVal, setStockVal] = useState('')

  useEffect(() => {
    if (open) {
      listSuppliers().then(setSuppliers).catch(() => {})
      listCategories().then(setCategories).catch(() => {})
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const t = setTimeout(() => {
      searchProducts({
        q,
        supplier_id: supplierId ? Number(supplierId) : undefined,
        category_id: categoryId ? Number(categoryId) : undefined,
        page,
      })
        .then((r) => {
          setItems(r.items)
          setTotal(r.total)
        })
        .catch(() => {})
    }, 300)
    return () => clearTimeout(t)
  }, [q, supplierId, categoryId, page, open])

  async function saveStock(id: number) {
    const num = Number(stockVal)
    if (isNaN(num)) return
    try {
      const r = await updateStock(id, num)
      setItems((prev) =>
        prev.map((it) =>
          it.product_id === id ? { ...it, stock: r.stock } : it
        )
      )
      setEditing(null)
    } catch (e: any) {
      alert(e.message)
    }
  }

  if (!open) return null

  return (
    <div
      className="panel p-4"
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: '80%',
        maxWidth: 800,
        overflow: 'auto',
      }}
    >
      <button onClick={onClose} style={{ float: 'right' }}>
        Cerrar
      </button>
      <h3>Consultar base</h3>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <input
          className="input w-full"
          placeholder="Buscar..."
          value={q}
          onChange={(e) => {
            setPage(1)
            setQ(e.target.value)
          }}
        />
        <select
          className="select"
          value={supplierId}
          onChange={(e) => {
            setSupplierId(e.target.value)
            setPage(1)
          }}
        >
          <option value="">Proveedor</option>
          {suppliers.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <select
          className="select"
          value={categoryId}
          onChange={(e) => {
            setCategoryId(e.target.value)
            setPage(1)
          }}
        >
          <option value="">Categoría</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <div style={{ fontSize: 12, marginBottom: 8 }}>
        {total} resultados
      </div>
      <table className="table w-full">
        <thead>
          <tr>
            <th>Producto</th>
            <th>Proveedor</th>
            <th>Precio venta</th>
            <th>Compra</th>
            <th>Stock</th>
            <th>Categoría</th>
            <th>Actualizado</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr key={it.product_id}>
              <td>{it.name}</td>
              <td>{it.supplier.name}</td>
              <td>{it.precio_venta ?? ''}</td>
              <td>{it.precio_compra ?? ''}</td>
              <td>
                {editing === it.product_id ? (
                  <span>
                    <input
                      type="number"
                      value={stockVal}
                      onChange={(e) => setStockVal(e.target.value)}
                      style={{ width: 60 }}
                    />
                    <button onClick={() => saveStock(it.product_id)}>Guardar</button>
                  </span>
                ) : (
                  <span>
                    {it.stock}
                    <button
                      onClick={() => {
                        setEditing(it.product_id)
                        setStockVal(String(it.stock))
                      }}
                      style={{ marginLeft: 4 }}
                    >
                      ✎
                    </button>
                  </span>
                )}
              </td>
              <td>{it.category_path}</td>
              <td>{it.updated_at ? new Date(it.updated_at).toLocaleString() : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
        <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
          Anterior
        </button>
        <button
          disabled={page * 20 >= total}
          onClick={() => setPage((p) => p + 1)}
        >
          Siguiente
        </button>
      </div>
    </div>
  )
}
