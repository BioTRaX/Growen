// NG-HEADER: Nombre de archivo: ProductsDrawer.tsx
// NG-HEADER: Ubicación: frontend/src/components/ProductsDrawer.tsx
// NG-HEADER: Descripción: Drawer de exploración y edición masiva de productos (búsqueda, filtros, edición y borrado en lote)
// NG-HEADER: Lineamientos: Ver AGENTS.md
// File consolidated below; removed duplicate earlier implementation
import { useEffect, useMemo, useState } from 'react'
import { FixedSizeList as List, ListChildComponentProps } from 'react-window'
import SupplierAutocomplete from './supplier/SupplierAutocomplete'
import type { SupplierSearchItem } from '../services/suppliers'
import { listCategories, Category, createCategory } from '../services/categories'
import { searchProducts, ProductItem, updateStock } from '../services/products'
import { deleteProducts } from '../services/products'
import ProductCreateModal from './ProductCreateModal'
import { updateSalePrice, updateSupplierSalePrice } from '../services/productsEx'
import { showToast } from './Toast'
import PriceHistoryModal from './PriceHistoryModal'
import CanonicalOffers from './CanonicalOffers'
import CanonicalForm from './CanonicalForm'
import EquivalenceLinker from './EquivalenceLinker'
import BulkSalePriceModal from './BulkSalePriceModal'
import ActivityPanel from './ActivityPanel'
import PriceEditModal from './PriceEditModal'
import DiagnosticsDrawer from './DiagnosticsDrawer'
import { useProductsTablePrefs } from '../lib/useTablePrefs'
import { formatARS, parseDecimalInput } from '../lib/format'
import { useAuth } from '../auth/AuthContext'
import { Link } from 'react-router-dom'
import { upsertEquivalence } from '../services/equivalences'

interface Props {
  open: boolean
  onClose: () => void
  mode?: 'overlay' | 'embedded'
}

export default function ProductsDrawer({ open, onClose, mode = 'overlay' }: Props) {
  const { state } = useAuth()
  const canEdit = state.role === 'admin' || state.role === 'colaborador'

  const [categories, setCategories] = useState<Category[]>([])
  const [supplierId, setSupplierId] = useState('')
  const [supplierSel, setSupplierSel] = useState<SupplierSearchItem | null>(null)
  const [categoryId, setCategoryId] = useState('')
  const [q, setQ] = useState('')
  const [items, setItems] = useState<ProductItem[]>([])
  const [page, setPage] = useState(1)
  const [pageSize] = useState(50)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [stockFilter, setStockFilter] = useState<string>('')
  const [recentFilter, setRecentFilter] = useState<string>('')
  const [typeFilter, setTypeFilter] = useState<'all' | 'canonical' | 'supplier'>('all')
  const [editing, setEditing] = useState<number | null>(null)
  const [stockVal, setStockVal] = useState('')
  const [saleEditing, setSaleEditing] = useState<number | null>(null) // canonical_product_id
  const [saleVal, setSaleVal] = useState('')
  const [editSupplierSaleId, setEditSupplierSaleId] = useState<number | null>(null)
  const [supplierSaleVal, setSupplierSaleVal] = useState('')
  const [historyProduct, setHistoryProduct] = useState<number | null>(null)
  const [canonicalId, setCanonicalId] = useState<number | null>(null)
  const [editCanonicalId, setEditCanonicalId] = useState<number | null>(null)
  const [equivData, setEquivData] = useState<{ supplierId: number; supplierProductId: number } | null>(null)
  const [createCanonicalCtx, setCreateCanonicalCtx] = useState<null | { initialName: string; supplierProductId: number; supplierId: number }>(null)
  const [selected, setSelected] = useState<number[]>([])
  const [showBulk, setShowBulk] = useState(false)
  const [activityFor, setActivityFor] = useState<number | null>(null)
  const [editingPriceFor, setEditingPriceFor] = useState<{ productId: number; canonicalId?: number | null; sale?: number | null } | null>(null)
  const [showColsCfg, setShowColsCfg] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [showDiag, setShowDiag] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [pendingDeleteIds, setPendingDeleteIds] = useState<number[] | null>(null)
  const [filling, setFilling] = useState(false)
  // New category/subcategory modals state
  const [showNewCat, setShowNewCat] = useState(false)
  const [newCatName, setNewCatName] = useState('')
  const [savingCat, setSavingCat] = useState(false)
  const [showNewSubcat, setShowNewSubcat] = useState(false)
  const [newSubcatName, setNewSubcatName] = useState('')
  const [newSubcatParent, setNewSubcatParent] = useState<number | ''>('')
  const [savingSubcat, setSavingSubcat] = useState(false)
  const selectAllOnPage = () => setSelected(items.map(i => i.product_id))
  const toggleSelectAllOnPage = () => setSelected((prev) => prev.length === items.length ? [] : items.map(i => i.product_id))
  // Fixed row height for virtualized list to avoid overlap
  const ROW_HEIGHT = 56
  const [listHeight, setListHeight] = useState<number>(400)
  // Forzar recarga aun si ya estamos en página 1
  const [reloadTick, setReloadTick] = useState(0)

  const { prefs, setPrefs, reset } = useProductsTablePrefs()

  type ColId =
    | 'select'
    | 'product'
    | 'sku'
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
    | 'actions'

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
    'sku',
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
    'actions',
  ]

  const defaultVisibility: Record<ColId, boolean> = {
    select: true,
    product: true,
    sku: true,
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
    actions: true,
  }

  const baseWidths: Record<ColId, number> = {
    select: 28,
    product: 300,
    sku: 140,
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
    actions: 120,
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
      listCategories().then(setCategories).catch(() => {})
    }
  }, [open])

  const topLevelCategories = useMemo(() => categories.filter(c => c.parent_id == null), [categories])

  async function handleCreateCategory() {
    const name = newCatName.trim()
    if (!name) return
    try {
      setSavingCat(true)
      await createCategory(name, null)
      showToast('success', 'Categoría creada')
      const list = await listCategories()
      setCategories(list)
      setShowNewCat(false)
      setNewCatName('')
    } catch (e: any) {
      showToast('error', e?.message || 'No se pudo crear la categoría')
    } finally {
      setSavingCat(false)
    }
  }

  async function handleCreateSubcategory() {
    const name = newSubcatName.trim()
    const parentId = typeof newSubcatParent === 'number' ? newSubcatParent : null
    if (!name || !parentId) return
    try {
      setSavingSubcat(true)
      await createCategory(name, parentId)
      showToast('success', 'Subcategoría creada')
      const list = await listCategories()
      setCategories(list)
      setShowNewSubcat(false)
      setNewSubcatName('')
      setNewSubcatParent('')
    } catch (e: any) {
      showToast('error', e?.message || 'No se pudo crear la subcategoría')
    } finally {
      setSavingSubcat(false)
    }
  }

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
        type: typeFilter,
        page,
        page_size: pageSize,
      })
        .then((r) => {
          setItems((prev) => (page === 1 ? r.items : [...prev, ...r.items]))
          setTotal(r.total)
        })
        .catch(() => {})
        .finally(() => setLoading(false))
    }, 300)
    return () => clearTimeout(t)
  }, [q, supplierId, categoryId, stockFilter, recentFilter, typeFilter, page, open, reloadTick])

  // Helper: refrescar lista (primera página) incluso si ya estamos en page=1
  const forceRefreshFirstPage = () => {
    setItems([])
    setPage(1)
    setReloadTick((t) => t + 1)
  }

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

  async function saveSupplierSalePrice(supplierItemId: number) {
    const parsed = parseDecimalInput(supplierSaleVal)
    if (parsed == null) return
    try {
      await updateSupplierSalePrice(supplierItemId, Number(parsed.toFixed(2)))
      setItems(prev => prev.map(it => ((it as any).supplier_item_id === supplierItemId ? { ...it, precio_venta: parsed } : it)))
      setEditSupplierSaleId(null)
      showToast('success', 'Precio de venta (proveedor) actualizado')
    } catch (e) {
      showToast('error', 'No se pudo actualizar el precio de venta (proveedor)')
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
        renderCell: (it) => {
          const skuDisplay = (it as any).canonical_sku || (it as any).first_variant_sku || ''
          return (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', maxWidth: widthFor('product') }}>
              <Link
                to={`/productos/${it.product_id}`}
                className="truncate product-title"
                style={{ display: 'inline-block', maxWidth: widthFor('product') }}
                title={it.name}
              >
                {it.name}
              </Link>
              {skuDisplay && (
                <span style={{ fontSize: 12, opacity: 0.8 }} title={skuDisplay}>
                  {skuDisplay}
                </span>
              )}
            </div>
          )
        },
      },
      {
        id: 'sku',
        label: 'SKU',
        defaultWidth: baseWidths.sku,
        renderCell: (it) => {
          const canonical = (it as any).canonical_sku as string | undefined
          const preferred = canonical || (it as any).first_variant_sku || ''
          return (
            <span className="truncate" style={{ display: 'inline-block', maxWidth: widthFor('sku') }} title={preferred}>
              {preferred}
              {canonical ? <span style={{ marginLeft: 6, fontSize: 11, opacity: 0.7 }}>(canónico)</span> : null}
            </span>
          )
        },
      },
      {
        id: 'supplier',
        label: 'Proveedor',
        defaultWidth: baseWidths.supplier,
        renderCell: (it) => <span>{it.supplier.name}</span>,
      },
      {
        id: 'sale_price',
        label: 'Precio venta',
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
            canEdit && (it as any).supplier_item_id ? (
              editSupplierSaleId === (it as any).supplier_item_id ? (
                <input
                  autoFocus
                  value={supplierSaleVal}
                  onChange={(e) => setSupplierSaleVal(e.target.value)}
                  onBlur={() => saveSupplierSalePrice((it as any).supplier_item_id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') saveSupplierSalePrice((it as any).supplier_item_id)
                    if (e.key === 'Escape') setEditSupplierSaleId(null)
                  }}
                  style={{ width: 100 }}
                />
              ) : (
                <span>
                  {formatARS((it as any).precio_venta)}
                  <button
                    onClick={() => {
                      setEditSupplierSaleId((it as any).supplier_item_id)
                      setSupplierSaleVal(String((it as any).precio_venta ?? ''))
                    }}
                    style={{ marginLeft: 6 }}
                  >
                    ✎
                  </button>
                </span>
              )
            ) : (
              <span>{formatARS((it as any).precio_venta)}</span>
            )
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
            <button onClick={() => { setCreateCanonicalCtx({ initialName: (it as any).supplier_title || it.name, supplierProductId: (it as any).supplier_item_id, supplierId: it.supplier.id }); setEditCanonicalId(0) }} disabled={!((it as any).supplier_item_id)}>
              Nuevo
            </button>
          )
        ),
      },
      {
        id: 'equivalence',
        label: 'Equivalencia',
        defaultWidth: baseWidths.equivalence,
        renderCell: (it) => (
          (it as any).supplier_item_id ? (
            <button
              onClick={() =>
                setEquivData({
                  supplierId: it.supplier.id,
                  supplierProductId: (it as any).supplier_item_id,
                })
              }
            >
              Vincular
            </button>
          ) : (
            <span style={{ opacity: 0.6 }}>—</span>
          )
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
      {
        id: 'actions',
        label: 'Acciones',
        defaultWidth: baseWidths.actions,
        renderCell: (it) => (
          canEdit ? (
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
              <button
                className="btn"
                onClick={() => setEditingPriceFor({ productId: it.product_id, canonicalId: it.canonical_product_id, sale: (it as any).canonical_sale_price ?? (it as any).precio_venta ?? null })}
              >Precio</button>
              <button className="btn" onClick={() => setActivityFor(it.product_id)}>Actividad</button>
              <button
                className="btn"
                onClick={() => { setPendingDeleteIds([it.product_id]); setShowDeleteConfirm(true) }}
              >Eliminar</button>
            </div>
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

  // Canonical IDs for bulk price editing (backend expects canonical_product_id)
  const selectedCanonicalIds = useMemo(() => {
    const sel = new Set(selected)
    const canon = items
      .filter(it => sel.has(it.product_id) && it.canonical_product_id)
      .map(it => it.canonical_product_id!)
    // unique
    return Array.from(new Set(canon))
  }, [items, selected])

  const isEmbedded = mode === 'embedded'
  const containerStyle: React.CSSProperties = mode === 'overlay' ? {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, width: '100%', maxWidth: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', zIndex: 20,
  } : {
    position: 'relative', width: '100%', display: 'flex', flexDirection: 'column', overflow: 'visible', margin: '16px auto', maxWidth: 1400,
  }

  return (
    <div className="panel p-4" style={containerStyle}>
      {/* Header actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        {mode === 'overlay' && (
          <button className="btn-dark btn-lg" onClick={onClose}>Volver</button>
        )}
        {!!selected.length && canEdit && (
          <button
            className="btn"
            onClick={() => {
              if (selectedCanonicalIds.length === 0) {
                showToast('info', 'Los seleccionados no tienen producto canónico. Vinculá equivalencias o abrí cada uno para editar precios a nivel proveedor.')
                return
              }
              if (selectedCanonicalIds.length < selected.length) {
                const skipped = selected.length - selectedCanonicalIds.length
                showToast('info', `Se omitirán ${skipped} sin canónico. Se editarán ${selectedCanonicalIds.length}.`)
              }
              setShowBulk(true)
            }}
          >
            Editar precios ({selected.length})
          </button>
        )}
        {
          <button
            className="btn"
            disabled={!selected.length}
            onClick={() => selected.length && setShowDeleteConfirm(true)}
          >
            Borrar seleccionados{selected.length ? ` (${selected.length})` : ''}
          </button>
        }
        <button
          className="btn"
          disabled={!items.length}
          onClick={toggleSelectAllOnPage}
        >
          {selected.length === items.length && items.length > 0 ? 'Deseleccionar página' : 'Seleccionar página'}
        </button>
        <button
          className="btn"
          disabled={!selected.length}
          onClick={() => setSelected([])}
        >
          Limpiar selección
        </button>
        <button className="btn" onClick={() => setShowColsCfg((v) => !v)}>Diseño</button>
  <button className="btn" onClick={() => reset()}>Restaurar diseño</button>
  <button className="btn" onClick={() => setShowDiag(true)}>Ver diagnósticos</button>
        {canEdit && (
          <button className="btn" onClick={() => setShowCreate(true)}>Nuevo producto</button>
        )}
        {canEdit && (
          <button className="btn" onClick={() => setShowNewCat(true)}>Nueva categoría</button>
        )}
        {canEdit && (
          <button className="btn" onClick={() => setShowNewSubcat(true)}>Nueva subcategoría</button>
        )}
        {canEdit && (
          <button
            className="btn"
            disabled={filling}
            onClick={async () => {
              setFilling(true)
              try {
                const headers: Record<string, string> = { 'Content-Type': 'application/json' }
                try {
                  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
                  if (m) headers['X-CSRF-Token'] = decodeURIComponent(m[1])
                } catch {}
                const res = await fetch('/products-ex/supplier-items/fill-missing-sale', {
                  method: 'POST',
                  credentials: 'include',
                  headers,
                  body: JSON.stringify({ supplier_id: supplierId ? Number(supplierId) : null }),
                })
                if (!res.ok) throw new Error(`HTTP ${res.status}`)
                const data = await res.json()
                showToast('success', `Precios de venta completados: ${data.updated}`)
                // Refrescar lista
                setPage(1)
                setItems([])
              } catch (e: any) {
                showToast('error', e?.message || 'No se pudo completar precios de venta')
              } finally {
                setFilling(false)
              }
            }}
          >
            Completar ventas faltantes
          </button>
        )}
        <div style={{ marginLeft: 'auto', fontSize: 12, opacity: 0.8 }}>
          Click en casillas para seleccionar filas
        </div>
      </div>
      {showColsCfg && <ColumnsCfg />}
      <h3 style={{ marginTop: 0 }}>Consultar base</h3>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <div className="btn-group" role="group" aria-label="Tipo">
          <button className={"btn" + (typeFilter === 'all' ? ' btn-dark' : '')} onClick={() => { setTypeFilter('all'); setItems([]); setPage(1) }}>Todos</button>
          <button className={"btn" + (typeFilter === 'canonical' ? ' btn-dark' : '')} onClick={() => { setTypeFilter('canonical'); setItems([]); setPage(1) }}>Canónicos</button>
          <button className={"btn" + (typeFilter === 'supplier' ? ' btn-dark' : '')} onClick={() => { setTypeFilter('supplier'); setItems([]); setPage(1) }}>Proveedor</button>
        </div>
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
        <SupplierAutocomplete
          className="input"
          value={supplierSel}
          onChange={(item) => {
            setSupplierSel(item)
            setSupplierId(item ? String(item.id) : '')
            setItems([])
            setPage(1)
          }}
          placeholder="Proveedor"
        />
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
      <div style={{ fontSize: 12, marginBottom: 8 }}>
        {total} resultados
        {isEmbedded && total > 0 && (
          <span style={{ marginLeft: 8, opacity: 0.8 }}>
            (Mostrando {Math.min(items.length, total)} de {total})
          </span>
        )}
      </div>
      {/* Horizontal scroll container */}
      <div style={{ flex: '1 1 auto', overflowX: 'auto', overflowY: isEmbedded ? 'visible' : 'hidden' }}>
        <div style={{ minWidth: orderedCols.reduce((sum, c) => sum + widthFor(c.id as ColId), 0) + 40 }}>
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
          {isEmbedded ? (
            <table className="table w-full table-fixed" style={{ marginBottom: 0 }}>
              <tbody>
                {items.map((it) => (
                  <tr key={it.product_id}>
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
                ))}
              </tbody>
            </table>
          ) : (
            <List
              height={listHeight}
              itemCount={items.length}
              itemSize={ROW_HEIGHT}
              width={orderedCols.reduce((sum, c) => sum + widthFor(c.id as ColId), 0) + 40}
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
          )}
        </div>
      </div>
      {/* Bottom scrollbar area only for overlay/virtualized mode */}
      {!isEmbedded && (
        <div style={{ height: 16, overflowX: 'auto' }}>
          <div style={{ width: orderedCols.reduce((sum, c) => sum + widthFor(c.id as ColId), 0) + 40 }} />
        </div>
      )}
      {/* Pagination controls for embedded mode */}
      {isEmbedded && (
        <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'center' }}>
          <button 
            className="btn-dark btn-lg" 
            disabled={page === 1 || loading} 
            onClick={() => {
              setPage(1)
              setItems([])
              window.scrollTo({ top: 0, behavior: 'smooth' })
            }}
          >
            Anterior
          </button>
          <button 
            className="btn-dark btn-lg" 
            disabled={items.length >= total || loading} 
            onClick={() => setPage((p) => p + 1)}
          >
            Más
          </button>
        </div>
      )}
      {historyProduct && (
        <PriceHistoryModal productId={historyProduct} onClose={() => setHistoryProduct(null)} />
      )}
      {canonicalId && <CanonicalOffers canonicalId={canonicalId} onClose={() => setCanonicalId(null)} />}
      {editCanonicalId !== null && (
        <CanonicalForm
          canonicalId={editCanonicalId || undefined}
          initialName={createCanonicalCtx?.initialName}
          onClose={() => { setEditCanonicalId(null); setCreateCanonicalCtx(null) }}
          onSaved={async (cp) => {
            try {
              if (createCanonicalCtx?.supplierProductId && createCanonicalCtx?.supplierId && cp?.id) {
                await upsertEquivalence({ supplier_id: createCanonicalCtx.supplierId, supplier_product_id: createCanonicalCtx.supplierProductId, canonical_product_id: cp.id, source: 'manual' })
              }
            } catch (e) {
              console.warn('Autovinculación falló', e)
            } finally {
              setEditCanonicalId(null)
              setCreateCanonicalCtx(null)
              // Refrescar lista volviendo a página 1 (forzar refetch)
              forceRefreshFirstPage()
            }
          }}
        />
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
          productIds={selectedCanonicalIds}
          onClose={(updated) => {
            setShowBulk(false)
            if (updated != null) {
              // Limpiar selección y refrescar la lista para reflejar nuevos precios
              setSelected([])
              forceRefreshFirstPage()
            }
          }}
        />
      )}
      {showCreate && (
        <ProductCreateModal
          onCreated={() => {
            // Refrescar lista volviendo a página 1 (forzar refetch)
            forceRefreshFirstPage()
            setShowCreate(false)
          }}
          onClose={() => setShowCreate(false)}
        />
      )}
      {editingPriceFor && (
        <PriceEditModal
          productId={editingPriceFor.productId}
          canonicalProductId={editingPriceFor.canonicalId}
          currentSale={editingPriceFor.sale ?? undefined}
          onSaved={(kind, value) => {
            // Update row minimally
            setItems(prev => prev.map(it => {
              if (it.product_id !== editingPriceFor.productId) return it
              if (kind === 'sale' && editingPriceFor?.canonicalId) {
                return { ...it, canonical_sale_price: value }
              }
              if (kind === 'buy') {
                return it // buy price not displayed in main list per-offering; skip
              }
              return it
            }))
          }}
          onClose={() => setEditingPriceFor(null)}
        />
      )}
      {activityFor && (
        <ActivityPanel productId={activityFor} onClose={() => setActivityFor(null)} />
      )}
      <DiagnosticsDrawer open={showDiag} onClose={() => setShowDiag(false)} />
      {showNewCat && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: 440 }}>
            <h3 style={{ marginTop: 0 }}>Nueva categoría</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 14 }}>Nombre</label>
              <input
                className="input"
                value={newCatName}
                onChange={(e) => setNewCatName(e.target.value)}
                placeholder="Ej: Fertilizantes"
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
              <button className="btn" disabled={savingCat} onClick={() => setShowNewCat(false)}>Cancelar</button>
              <button className="btn-dark" disabled={savingCat || !newCatName.trim()} onClick={handleCreateCategory}>Crear</button>
            </div>
          </div>
        </div>
      )}
      {showNewSubcat && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: 480 }}>
            <h3 style={{ marginTop: 0 }}>Nueva subcategoría</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 14 }}>Categoría padre</label>
              <select
                className="select"
                value={newSubcatParent === '' ? '' : String(newSubcatParent)}
                onChange={(e) => setNewSubcatParent(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">Seleccionar</option>
                {topLevelCategories.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <label style={{ fontSize: 14 }}>Nombre</label>
              <input
                className="input"
                value={newSubcatName}
                onChange={(e) => setNewSubcatName(e.target.value)}
                placeholder="Ej: Líquidos"
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
              <button className="btn" disabled={savingSubcat} onClick={() => setShowNewSubcat(false)}>Cancelar</button>
              <button
                className="btn-dark"
                disabled={savingSubcat || !newSubcatName.trim() || typeof newSubcatParent !== 'number'}
                onClick={handleCreateSubcategory}
              >
                Crear
              </button>
            </div>
          </div>
        </div>
      )}
      {showDeleteConfirm && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: 440 }}>
            <h3 style={{ marginTop: 0 }}>Confirmar borrado</h3>
            <p style={{ fontSize: 14 }}>
              Vas a borrar <strong>{(pendingDeleteIds ?? selected).length}</strong> producto(s). Esta acción es permanente y puede eliminar o dejar huérfanas
              referencias asociadas (imágenes, equivalencias, etc.) según las reglas del backend. No se puede deshacer.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
              <button className="btn" disabled={deleting} onClick={() => setShowDeleteConfirm(false)}>Cancelar</button>
              <button
                className="btn-dark"
                disabled={deleting || !(pendingDeleteIds ?? selected).length}
                onClick={async () => {
                  const ids = (pendingDeleteIds ?? selected).slice()
                  if (!ids.length) return
                  setDeleting(true)
                  try {
                    // Pre-chequeo amigable: avisar si hay seleccionados con stock > 0
                    try {
                      const selSet = new Set(ids)
                      const withStock = items.filter(it => selSet.has(it.product_id) && (it.stock ?? 0) > 0)
                      if (withStock.length > 0) {
                        const showCount = Math.min(5, withStock.length)
                        const sample = withStock.slice(0, showCount).map(it => String(it.product_id)).join(', ')
                        showToast('info', `Seleccionaste ${withStock.length} con stock > 0${withStock.length ? ` (ej: ${sample}${withStock.length > showCount ? '…' : ''})` : ''}. El backend bloqueará esos borrados.`)
                      }
                    } catch {}
                    const r = await deleteProducts(ids)
                    let msg = `Borrados ${r.deleted.length} de ${r.requested.length}`
                    const blockedMessages: string[] = []
                    if (r.blocked_stock?.length) {
                      const showCount = Math.min(5, r.blocked_stock.length)
                      const sample = r.blocked_stock.slice(0, showCount).join(', ')
                      blockedMessages.push(`con stock: ${r.blocked_stock.length}${r.blocked_stock.length ? ` (ej: ${sample}${r.blocked_stock.length > showCount ? '…' : ''})` : ''}`)
                    }
                    if (r.blocked_refs?.length) {
                      const showCount = Math.min(5, r.blocked_refs.length)
                      const sample = r.blocked_refs.slice(0, showCount).join(', ')
                      blockedMessages.push(`con referencias: ${r.blocked_refs.length}${r.blocked_refs.length ? ` (ej: ${sample}${r.blocked_refs.length > showCount ? '…' : ''})` : ''}`)
                    }
                    if (blockedMessages.length) {
                      msg += ` (Bloqueados: ${blockedMessages.join(', ')})`
                    }
                    showToast(r.deleted.length > 0 ? 'success' : 'info', msg)
                    if ((r.blocked_stock?.length || 0) + (r.blocked_refs?.length || 0)) {
                      showToast('info', 'Sugerencia: filtrá "Sin stock" para facilitar el borrado de los que quedaron bloqueados por stock.')
                    }
                    
                    if (r.deleted.length > 0) {
                      setItems(prev => prev.filter(it => !r.deleted.includes(it.product_id)))
                    }
                    setSelected(prev => prev.filter(id => !r.deleted.includes(id)))
                    setPendingDeleteIds(null)
                    setShowDeleteConfirm(false)
                    
                    // If the list becomes empty after deletion, force a refresh of the first page
                    if (items.length === r.deleted.length) {
                      setTimeout(() => {
                        setPage(1)
                        setItems([])
                      }, 100)
                    }
                  } catch (e: any) {
                    showToast('error', e?.message || 'No se pudieron eliminar los productos')
                  } finally {
                    setDeleting(false)
                  }
                }}
              >
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
