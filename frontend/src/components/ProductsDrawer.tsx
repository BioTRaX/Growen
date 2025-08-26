import { useEffect, useState } from 'react'
import {
  FixedSizeList as List,
  ListChildComponentProps,
} from 'react-window'
import { listSuppliers, Supplier } from '../services/suppliers'
import { listCategories, Category } from '../services/categories'
import {
  searchProducts,
  ProductItem,
  updateStock,
} from '../services/products'
import PriceHistoryModal from './PriceHistoryModal'
import CanonicalOffers from './CanonicalOffers'
import CanonicalForm from './CanonicalForm'
import EquivalenceLinker from './EquivalenceLinker'

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
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState<number | null>(null)
  const [stockVal, setStockVal] = useState('')
  const [historyProduct, setHistoryProduct] = useState<number | null>(null)
  const [canonicalId, setCanonicalId] = useState<number | null>(null)
  const [editCanonicalId, setEditCanonicalId] = useState<number | null>(null)
  const [equivData, setEquivData] = useState<
    { supplierId: number; supplierProductId: number } | null
  >(null)
  // Fixed row height for virtualized list to avoid overlap
  const ROW_HEIGHT = 56
  const [listHeight, setListHeight] = useState<number>(400)

  useEffect(() => {
    function recalc() {
      const headerH = 56
      const titleH = 32
      const filterH = 56
      const metaH = 24
      const theadH = 44
      const padding = 24 + 24
      const h = window.innerHeight - (headerH + titleH + filterH + metaH + theadH + padding)
      setListHeight(Math.max(240, h))
    }
    recalc()
    window.addEventListener('resize', recalc)
    return () => window.removeEventListener('resize', recalc)
  }, [])

  useEffect(() => {
    if (open) {
      listSuppliers().then(setSuppliers).catch(() => {})
      listCategories().then(setCategories).catch(() => {})
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const t = setTimeout(() => {
      setLoading(true)
      searchProducts({
        q,
        supplier_id: supplierId ? Number(supplierId) : undefined,
        category_id: categoryId ? Number(categoryId) : undefined,
        page,
      })
        .then((r) => {
          setItems((prev) => (page === 1 ? r.items : [...prev, ...r.items]))
          setTotal(r.total)
        })
        .catch(() => {})
        .finally(() => setLoading(false))
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
        left: 0,
        right: 0,
        bottom: 0,
        width: '100%',
        maxWidth: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        zIndex: 20,
      }}
    >
      {/* Header actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <button className="btn-dark btn-lg" onClick={onClose}>Volver</button>
      </div>
      <h3 style={{ marginTop: 0 }}>Consultar base</h3>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <input
          className="input w-full"
          placeholder="Buscar..."
          value={q}
          onChange={(e) => {
            setPage(1)
            setItems([])
            setQ(e.target.value)
          }}
        />
        <select
          className="select"
          value={supplierId}
          onChange={(e) => {
            setSupplierId(e.target.value)
            setItems([])
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
            setItems([])
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
  <table className="table w-full table-fixed" style={{ marginBottom: 0 }}>
        <thead>
          <tr>
    <th style={{ textAlign: 'left' }}>Producto</th>
    <th style={{ textAlign: 'left' }}>Proveedor</th>
    <th className="text-center">Precio venta</th>
    <th className="text-center">Compra</th>
    <th className="text-center">Stock</th>
    <th className="text-center">Categoría</th>
    <th className="text-center">Actualizado</th>
    <th className="text-center">Historial</th>
    <th className="text-center">Canónico</th>
    <th className="text-center">Equivalencia</th>
    <th className="text-center">Comparativa</th>
          </tr>
        </thead>
      </table>
      <List
        height={listHeight}
        itemCount={items.length}
        itemSize={ROW_HEIGHT}
        width={"100%"}
        onItemsRendered={({ visibleStopIndex }) => {
          if (
            visibleStopIndex >= items.length - 5 &&
            !loading &&
            items.length < total
          ) {
            setPage((p) => p + 1)
          }
        }}
      >
        {({ index, style }: ListChildComponentProps) => {
          const it = items[index]
          return (
            <div key={it.product_id} style={{ ...style, height: ROW_HEIGHT, overflow: 'hidden' }}>
              <table className="table w-full table-fixed" style={{ marginBottom: 0 }}>
                <tbody>
                  <tr>
                  <td style={{ textAlign: 'left', maxWidth: 300 }} className="truncate">{it.name}</td>
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
                  <td className="text-center truncate" style={{ maxWidth: 280 }}>{it.category_path}</td>
      <td className="text-center">
                    {it.updated_at
                      ? new Date(it.updated_at).toLocaleString()
                      : ''}
                  </td>
      <td className="text-center">
                    <button onClick={() => setHistoryProduct(it.product_id)}>
                      Ver
                    </button>
                  </td>
      <td className="text-center">
                    {it.canonical_product_id ? (
                      <button
                        onClick={() => setEditCanonicalId(it.canonical_product_id)}
                      >
                        Editar
                      </button>
                    ) : (
                      <button onClick={() => setEditCanonicalId(0)}>Nuevo</button>
                    )}
                  </td>
      <td className="text-center">
                    <button
                      onClick={() =>
                        setEquivData({
                          supplierId: it.supplier.id,
                          supplierProductId: it.product_id,
                        })
                      }
                    >
                      Vincular
                    </button>
                  </td>
      <td className="text-center">
                    {it.canonical_product_id && (
                      <button onClick={() => setCanonicalId(it.canonical_product_id)}>
                        Ver
                      </button>
                    )}
                  </td>
                  </tr>
                </tbody>
              </table>
            </div>
          )
        }}
      </List>
      {historyProduct && (
        <PriceHistoryModal
          productId={historyProduct}
          onClose={() => setHistoryProduct(null)}
        />
      )}
      {canonicalId && (
        <CanonicalOffers canonicalId={canonicalId} onClose={() => setCanonicalId(null)} />
      )}
      {editCanonicalId !== null && (
        <CanonicalForm
          canonicalId={editCanonicalId || undefined}
          onClose={() => setEditCanonicalId(null)}
        />
      )}
      {equivData && (
        <EquivalenceLinker
          supplierId={equivData.supplierId}
          supplierProductId={equivData.supplierProductId}
          onClose={() => setEquivData(null)}
        />
      )}
    </div>
  )
}
