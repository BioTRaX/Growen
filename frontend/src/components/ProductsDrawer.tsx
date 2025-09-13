// NG-HEADER: Nombre de archivo: ProductsDrawer.tsx
// NG-HEADER: Ubicación: frontend/src/components/ProductsDrawer.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
// File consolidated below; removed duplicate earlier implementation
import { useEffect, useMemo, useState } from 'react'
import { FixedSizeList as List, ListChildComponentProps } from 'react-window'
import { listSuppliers, Supplier } from '../services/suppliers'
import { listCategories, Category } from '../services/categories'
import { searchProducts, ProductItem, updateStock } from '../services/products'
import { deleteProducts } from '../services/products'
import ProductCreateModal from './ProductCreateModal'
import { updateSalePrice } from '../services/productsEx'
import { showToast } from './Toast'
import PriceHistoryModal from './PriceHistoryModal'
import CanonicalOffers from './CanonicalOffers'
import CanonicalForm from './CanonicalForm'
import EquivalenceLinker from './EquivalenceLinker'
import BulkSalePriceModal from './BulkSalePriceModal'
import { useProductsTablePrefs } from '../lib/useTablePrefs'
import { formatARS, parseDecimalInput } from '../lib/format'
import { useAuth } from '../auth/AuthContext'
import { Link } from 'react-router-dom'

interface Props {
  open: boolean
  onClose: () => void
}

export default function ProductsDrawer({ open, onClose }: Props) {
  const { state } = useAuth()
  const canEdit = state.role === 'admin' || state.role === 'colaborador'

  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [supplierId, setSupplierId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [q, setQ] = useState('')
  const [items, setItems] = useState<ProductItem[]>([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [stockFilter, setStockFilter] = useState<string>('')
  const [recentFilter, setRecentFilter] = useState<string>('')
  const [editing, setEditing] = useState<number | null>(null)
  const [stockVal, setStockVal] = useState('')
  const [saleEditing, setSaleEditing] = useState<number | null>(null) // canonical_product_id
  const [saleVal, setSaleVal] = useState('')
  const [historyProduct, setHistoryProduct] = useState<number | null>(null)
  const [canonicalId, setCanonicalId] = useState<number | null>(null)
  const [editCanonicalId, setEditCanonicalId] = useState<number | null>(null)
  const [equivData, setEquivData] = useState<{ supplierId: number; supplierProductId: number } | null>(null)
  const [selected, setSelected] = useState<number[]>([])
  const [showBulk, setShowBulk] = useState(false)
  const [showColsCfg, setShowColsCfg] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  // Fixed row height for virtualized list to avoid overlap
  const ROW_HEIGHT = 56
  const [listHeight, setListHeight] = useState<number>(400)

  const { prefs, setPrefs, reset } = useProductsTablePrefs()

  type ColId =
    | 'select'
    | 'product'
    | 'supplier'
    | 'sale_price'
    | 'buy_price'
    | 'stock'
    | 'category'
    | 'updated_at'
    | 'history'
    | 'canonical'
    | 'equivalence'
    | 'comparativa'

  type ColDef = {
    id: ColId
    label: string
    defaultWidth: number
    renderHeader?: () => JSX.Element
    renderCell: (it: ProductItem) => JSX.Element
  }

  const defaultOrder: ColId[] = [
    'select',
    'product',
    'supplier',
    'sale_price',
    'buy_price',
    'stock',
    'category',
    'updated_at',
    'history',
    'canonical',
    'equivalence',
    'comparativa',
  ]

  const defaultVisibility: Record<ColId, boolean> = {
    select: true,
    product: true,
    supplier: true,
    sale_price: true,
    buy_price: true,
    stock: true,
    category: true,
    updated_at: true,
    history: true,
    canonical: true,
    equivalence: true,
    comparativa: true,
  }

  const baseWidths: Record<ColId, number> = {
    select: 28,
    product: 300,
    supplier: 160,
    sale_price: 140,
    buy_price: 120,
    stock: 120,
    category: 260,
    updated_at: 160,
    history: 100,
    canonical: 110,
    equivalence: 120,
    comparativa: 110,
  }

  function widthFor(id: ColId): number {
    const w = (prefs?.columnWidths as any)?.[id]
    return typeof w === 'number' && w > 24 ? w : baseWidths[id]
  }

  function isVisible(id: ColId): boolean {
    const vis = (prefs?.columnVisibility as any)?.[id]
    const fallback = defaultVisibility[id]
    return typeof vis === 'boolean' ? vis : fallback
  }

  const updatePrefs = (upd: Partial<{ columnOrder: ColId[]; columnVisibility: Record<ColId, boolean>; columnWidths: Record<ColId, number> }>) => {
    const next = {
      columnOrder: (upd.columnOrder || (prefs?.columnOrder as any) || defaultOrder) as string[],
      columnVisibility: (upd.columnVisibility || (prefs?.columnVisibility as any) || defaultVisibility) as Record<string, boolean>,
      columnWidths: (upd.columnWidths || (prefs?.columnWidths as any) || {}) as Record<string, number>,
    }
    setPrefs(next)
  }

  const ColumnsCfg = () => {
    const order = ((prefs?.columnOrder as any) as ColId[]) || defaultOrder
    const visibility = ((prefs?.columnVisibility as any) as Record<ColId, boolean>) || defaultVisibility
    const widths = ((prefs?.columnWidths as any) as Record<ColId, number>) || {}
    const move = (id: ColId, dir: -1 | 1) => {
      const idx = order.indexOf(id)
      const j = idx + dir
      if (idx < 0 || j < 0 || j >= order.length) return
      const next = order.slice()
      const [x] = next.splice(idx, 1)
      next.splice(j, 0, x)
      updatePrefs({ columnOrder: next })
    }
    const toggle = (id: ColId) => {
      updatePrefs({ columnVisibility: { ...visibility, [id]: !isVisible(id) } })
    }
    const setW = (id: ColId, v: number) => {
      const w = Math.max(28, Math.min(640, Math.floor(v)))
      updatePrefs({ columnWidths: { ...widths, [id]: w } })
    }
    return (
      <div className="panel" style={{ position: 'absolute', right: 16, top: 64, padding: 12, zIndex: 30, width: 380 }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <strong style={{ flex: 1 }}>Diseño de tabla</strong>
          <button className="btn" onClick={() => setShowColsCfg(false)}>Cerrar</button>
        </div>
        <div style={{ fontSize: 12, opacity: 0.8, margin: '6px 0 8px' }}>
          Mostrar/ocultar, reordenar y ajustar anchos. Se guarda por usuario.
        </div>
        <div style={{ maxHeight: 280, overflow: 'auto' }}>
          {order.map((id) => (
            <div key={id} style={{ display: 'grid', gridTemplateColumns: '20px 1fr 84px 56px 56px', alignItems: 'center', gap: 8, padding: '4px 0' }}>
              <input type="checkbox" checked={isVisible(id)} onChange={() => toggle(id)} />
              <span style={{ textTransform: 'capitalize' }}>{id.replace('_', ' ')}</span>
              <input
                className="input"
                type="number"
                value={widths[id] ?? baseWidths[id]}
                onChange={(e) => setW(id, Number(e.target.value))}
              />
              <button className="btn" onClick={() => move(id, -1)}>↑</button>
              <button className="btn" onClick={() => move(id, +1)}>↓</button>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
          <button className="btn" onClick={() => reset()}>Restaurar diseño</button>
        </div>
      </div>
    )
  }

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
        stock: stockFilter || undefined,
        created_since_days: recentFilter ? Number(recentFilter) : undefined,
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
  }, [q, supplierId, categoryId, stockFilter, recentFilter, page, open])

  async function saveStock(id: number) {
    const num = Number(stockVal)
    if (isNaN(num)) return
    try {
      const r = await updateStock(id, num)
      setItems((prev) => prev.map((it) => (it.product_id === id ? { ...it, stock: r.stock } : it)))
      setEditing(null)
    } catch (e: any) {
      alert(e.message)
    }
  }

  async function saveSalePrice(canonicalId: number) {
    const parsed = parseDecimalInput(saleVal)
    if (parsed == null) return
    try {
      const r = await updateSalePrice(canonicalId, Number(parsed.toFixed(2)))
      setItems((prev) => prev.map((it) => (it.canonical_product_id === canonicalId ? { ...it, canonical_sale_price: r.sale_price ?? null } : it)))
      setSaleEditing(null)
      showToast('success', 'Precio de venta actualizado')
    } catch (e) {
      showToast('error', 'No se pudo guardar el precio de venta')
    }
  }

  if (!open) return null

  // Column definitions
  const colDefs: ColDef[] = useMemo(() => {
    const defs: ColDef[] = [
      {
        id: 'select',
        label: '',
        defaultWidth: baseWidths.select,
        renderCell: (it) => (
          <input
            type="checkbox"
            checked={selected.includes(it.product_id)}
            onChange={(e) =>
              setSelected((prev) => (e.target.checked ? [...prev, it.product_id] : prev.filter((id) => id !== it.product_id)))
            }
          />
        ),
      },
      {
        id: 'product',
        label: 'Producto',
        defaultWidth: baseWidths.product,
        renderCell: (it) => (
          <Link to={`/productos/${it.product_id}`} className="truncate" style={{ display: 'inline-block', maxWidth: widthFor('product') }}>
            {it.name}
          </Link>
        ),
      },
      {
        id: 'supplier',
        label: 'Proveedor',
        defaultWidth: baseWidths.supplier,
        renderCell: (it) => <span>{it.supplier.name}</span>,
      },
      {
        id: 'sale_price',
        label: 'Precio venta (canónico)',
        defaultWidth: baseWidths.sale_price,
        renderCell: (it) => (
          it.canonical_product_id ? (
            saleEditing === it.canonical_product_id ? (
              <input
                autoFocus
                value={saleVal}
                onChange={(e) => setSaleVal(e.target.value)}
                onBlur={() => saveSalePrice(it.canonical_product_id!)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') saveSalePrice(it.canonical_product_id!)
                  if (e.key === 'Escape') setSaleEditing(null)
                }}
                style={{ width: 100 }}
                disabled={!canEdit}
              />
            ) : (
              <span>
                {formatARS((it as any).canonical_sale_price ?? (it as any).precio_venta)}
                {canEdit && (
                  <button
                    onClick={() => {
                      setSaleEditing(it.canonical_product_id!)
                      const v = (it as any).canonical_sale_price ?? (it as any).precio_venta
                      setSaleVal(v != null ? String(v) : '')
                    }}
                    style={{ marginLeft: 6 }}
                  >
                    ✎
                  </button>
                )}
              </span>
            )
          ) : (
            <span style={{ opacity: 0.6 }}>—</span>
          )
        ),
      },
      {
        id: 'buy_price',
        label: 'Compra',
        defaultWidth: baseWidths.buy_price,
        renderCell: (it) => <span>{formatARS((it as any).precio_compra)}</span>,
      },
      {
        id: 'stock',
        label: 'Stock',
        defaultWidth: baseWidths.stock,
        renderCell: (it) => (
          editing === it.product_id ? (
            <span>
              <input type="number" value={stockVal} onChange={(e) => setStockVal(e.target.value)} style={{ width: 60 }} />
              <button onClick={() => saveStock(it.product_id)}>Guardar</button>
            </span>
          ) : (
            <span>
              {it.stock}
              {canEdit && (
                <button
                  onClick={() => {
                    setEditing(it.product_id)
                    setStockVal(String(it.stock))
                  }}
                  style={{ marginLeft: 4 }}
                >
                  ✎
                </button>
              )}
            </span>
          )
        ),
      },
      {
        id: 'category',
        label: 'Categoría',
        defaultWidth: baseWidths.category,
        renderCell: (it) => <span className="truncate" style={{ display: 'inline-block', maxWidth: widthFor('category') }}>{it.category_path}</span>,
      },
      {
        id: 'updated_at',
        label: 'Actualizado',
        defaultWidth: baseWidths.updated_at,
        renderCell: (it) => <span>{it.updated_at ? new Date(it.updated_at).toLocaleString() : ''}</span>,
      },
      {
        id: 'history',
        label: 'Historial',
        defaultWidth: baseWidths.history,
        renderCell: (it) => <button onClick={() => setHistoryProduct(it.product_id)}>Ver</button>,
      },
      {
        id: 'canonical',
        label: 'Canónico',
        defaultWidth: baseWidths.canonical,
        renderCell: (it) => (
          it.canonical_product_id ? (
            <button onClick={() => setEditCanonicalId(it.canonical_product_id)}>Editar</button>
          ) : (
            <button onClick={() => setEditCanonicalId(0)}>Nuevo</button>
          )
        ),
      },
      {
        id: 'equivalence',
        label: 'Equivalencia',
        defaultWidth: baseWidths.equivalence,
        renderCell: (it) => (
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
        ),
      },
      {
        id: 'comparativa',
        label: 'Comparativa',
        defaultWidth: baseWidths.comparativa,
        renderCell: (it) => (
          it.canonical_product_id ? (
            <button onClick={() => setCanonicalId(it.canonical_product_id)}>Ver</button>
          ) : (
            <span />
          )
        ),
      },
    ]
    return defs
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, saleEditing, saleVal, editing, stockVal, prefs, canEdit])

  const orderedCols: ColDef[] = useMemo(() => {
    const order = ((prefs?.columnOrder as any) as ColId[]) || defaultOrder
    const vis = ((prefs?.columnVisibility as any) as Record<ColId, boolean>) || defaultVisibility
    const map: Record<string, ColDef> = Object.fromEntries(colDefs.map((c) => [c.id, c]))
    return order.map((id) => map[id]).filter((c) => c && (vis as any)[c.id] !== false)
  }, [colDefs, prefs])

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
        {!!selected.length && canEdit && (
          <button className="btn" onClick={() => setShowBulk(true)}>
            Editar precios ({selected.length})
          </button>
        )}
        {!!selected.length && canEdit && (
          <button
            className="btn"
            onClick={async () => {
              if (!window.confirm(`Eliminar ${selected.length} productos? Esta acción es permanente.`)) return
              try {
                await deleteProducts(selected)
                // refrescar lista
                setItems([])
                setPage(1)
                setSelected([])
              } catch (e) {
                alert('No se pudieron eliminar')
              }
            }}
          >
            Eliminar seleccionados
          </button>
        )}
        <button className="btn" onClick={() => setShowColsCfg((v) => !v)}>Diseño</button>
        <button className="btn" onClick={() => reset()}>Restaurar diseño</button>
        {canEdit && (
          <button className="btn" onClick={() => setShowCreate(true)}>Nuevo producto</button>
        )}
        <div style={{ marginLeft: 'auto', fontSize: 12, opacity: 0.8 }}>
          Click en casillas para seleccionar filas
        </div>
      </div>
      {showColsCfg && <ColumnsCfg />}
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
        <select
          className="select"
          value={stockFilter}
          onChange={(e) => {
            setStockFilter(e.target.value)
            setItems([])
            setPage(1)
          }}
        >
          <option value="">Stock: Todos</option>
          <option value="gt:0">Con stock</option>
          <option value="eq:0">Sin stock</option>
        </select>
        <select
          className="select"
          value={recentFilter}
          onChange={(e) => {
            setRecentFilter(e.target.value)
            setItems([])
            setPage(1)
          }}
        >
          <option value="">Recientes: Todos</option>
          <option value="1">Últimas 24h</option>
          <option value="7">≤ 7 días</option>
          <option value="30">≤ 30 días</option>
        </select>
      </div>
      <div style={{ fontSize: 12, marginBottom: 8 }}>{total} resultados</div>
      <table className="table w-full table-fixed" style={{ marginBottom: 0 }}>
        <thead>
          <tr>
            {orderedCols.map((c) => (
              <th
                key={c.id}
                style={{ width: widthFor(c.id as ColId), textAlign: c.id === 'product' || c.id === 'supplier' ? 'left' : 'center' }}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
      </table>
      <List
        height={listHeight}
        itemCount={items.length}
        itemSize={ROW_HEIGHT}
        width={"100%"}
        onItemsRendered={({ visibleStopIndex }) => {
          if (visibleStopIndex >= items.length - 5 && !loading && items.length < total) {
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
                    {orderedCols.map((c) => (
                      <td
                        key={c.id}
                        className={c.id === 'product' || c.id === 'supplier' ? '' : 'text-center'}
                        style={{ width: widthFor(c.id as ColId) }}
                      >
                        {c.renderCell(it)}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          )
        }}
      </List>
      {historyProduct && (
        <PriceHistoryModal productId={historyProduct} onClose={() => setHistoryProduct(null)} />
      )}
      {canonicalId && <CanonicalOffers canonicalId={canonicalId} onClose={() => setCanonicalId(null)} />}
      {editCanonicalId !== null && (
        <CanonicalForm canonicalId={editCanonicalId || undefined} onClose={() => setEditCanonicalId(null)} />
      )}
      {equivData && (
        <EquivalenceLinker
          supplierId={equivData.supplierId}
          supplierProductId={equivData.supplierProductId}
          onClose={() => setEquivData(null)}
        />
      )}
      {showBulk && (
        <BulkSalePriceModal
          productIds={selected}
          onClose={(updated) => {
            setShowBulk(false)
            if (updated != null) {
              setSelected([])
            }
          }}
        />
      )}
      {showCreate && (
        <ProductCreateModal
          onCreated={() => {
            // Refrescar lista volviendo a página 1
            setPage(1)
            setItems([])
            setShowCreate(false)
          }}
          onClose={() => setShowCreate(false)}
        />
      )}
    </div>
  )
}
