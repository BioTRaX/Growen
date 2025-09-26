// NG-HEADER: Nombre de archivo: Stock.tsx
// NG-HEADER: Ubicación: frontend/src/pages/Stock.tsx
// NG-HEADER: Descripción: Página de stock y existencias.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import type { SupplierSearchItem } from '../services/suppliers'
import SupplierAutocomplete from '../components/supplier/SupplierAutocomplete'
import { useNavigate } from 'react-router-dom'
import { PATHS } from '../routes/paths'
import { listCategories, Category } from '../services/categories'
import { searchProducts, ProductItem, updateStock, deleteProducts } from '../services/products'
import { updateSalePrice, updateSupplierBuyPrice, updateSupplierSalePrice } from '../services/productsEx'
import { useAuth } from '../auth/AuthContext'
import { pushTNBulk } from '../services/images'
import { generateCatalog, headLatestCatalog } from '../services/catalogs'
import { baseURL as base } from '../services/http'
import CatalogHistoryModal from '../components/CatalogHistoryModal'
import { useToast } from '../components/ToastProvider'

export default function Stock() {
  const { push } = useToast()
  const { state } = useAuth()
  const canEdit = state.role === 'admin' || state.role === 'colaborador'
  const navigate = useNavigate()
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
  const [editing, setEditing] = useState<number | null>(null)
  const [stockVal, setStockVal] = useState('')
  const [editSaleId, setEditSaleId] = useState<number | null>(null)
  const [saleVal, setSaleVal] = useState('')
  const [editSupplierSaleId, setEditSupplierSaleId] = useState<number | null>(null)
  const [supplierSaleVal, setSupplierSaleVal] = useState('')
  const [editBuyId, setEditBuyId] = useState<number | null>(null)
  const [buyVal, setBuyVal] = useState('')
  const [tab, setTab] = useState<'gt' | 'eq'>('gt')
  const [pushing, setPushing] = useState(false)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [showHistory, setShowHistory] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [filling, setFilling] = useState(false)
  const toggleSelect = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }
  const clearSelection = () => setSelected(new Set())
  const selectAllOnPage = () => setSelected(new Set(items.map((i) => i.product_id)))
  const toggleSelectAllOnPage = () => {
    if (selected.size === items.length) clearSelection(); else selectAllOnPage()
  }

  useEffect(() => {
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

  function parseDecimalInput(s: string): number | null {
    if (!s) return null
    const x = s.replace(/\s+/g, '').replace(',', '.')
    const num = Number(x)
    if (!isFinite(num) || num <= 0) return null
    return Math.round(num * 100) / 100
  }

  async function saveSalePrice(pid: number) {
    const v = parseDecimalInput(saleVal)
    if (v == null) { push({ kind: 'error', message: 'Precio de venta inválido' }); return }
    try {
      await updateSalePrice(pid, v)
      setItems(prev => prev.map(it => (it.canonical_product_id === pid ? { ...it, canonical_sale_price: v } : it)))
      push({ kind: 'success', message: 'Precio de venta actualizado' })
      setEditSaleId(null)
    } catch (e: any) {
      push({ kind: 'error', message: e.message || 'Error actualizando precio de venta' })
    }
  }

  async function saveSupplierSalePrice(supplierItemId: number) {
    const v = parseDecimalInput(supplierSaleVal)
    if (v == null) { push({ kind: 'error', message: 'Precio de venta inválido' }); return }
    try {
      await updateSupplierSalePrice(supplierItemId, v)
      setItems(prev => prev.map(it => (it as any).supplier_item_id === supplierItemId ? { ...it, precio_venta: v } : it))
      push({ kind: 'success', message: 'Precio de venta (proveedor) actualizado' })
      setEditSupplierSaleId(null)
    } catch (e: any) {
      push({ kind: 'error', message: e.message || 'Error actualizando precio de venta' })
    }
  }

  async function saveBuyPrice(supplierItemId: number) {
    const v = parseDecimalInput(buyVal)
    if (v == null) { push({ kind: 'error', message: 'Precio de compra inválido' }); return }
    try {
      await updateSupplierBuyPrice(supplierItemId, v)
      setItems(prev => prev.map(it => (it as any).supplier_item_id === supplierItemId ? { ...it, precio_compra: v } : it))
      push({ kind: 'success', message: 'Precio de compra actualizado' })
      setEditBuyId(null)
    } catch (e: any) {
      push({ kind: 'error', message: e.message || 'Error actualizando precio de compra' })
    }
  }

  return (
    <div className="panel p-4" style={{ margin: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
  <h2 style={{ marginTop: 0, marginBottom: 8, flex: 1 }}>Stock</h2>
  <div style={{ display: 'flex', gap: 8, flexWrap:'wrap' }}>
    <button className="btn-dark btn-lg" onClick={() => navigate(PATHS.purchases)}>Compras</button>
    <button className="btn" disabled={pushing || !items.length} onClick={async () => { setPushing(true); try { await pushTNBulk(items.map((i) => i.product_id)); alert('Push Tiendanube (stub) completado'); } finally { setPushing(false) } }}>Enviar imágenes a Tiendanube</button>
    <button className="btn" disabled={!selected.size} onClick={async () => {
      if (!selected.size) { push({ kind:'error', message:'Debe seleccionar al menos un producto' }); return }
      try { const rIds = Array.from(selected); await generateCatalog(rIds); push({ kind:'success', message:`Catálogo generado (${rIds.length} productos)` }) } catch (e:any) { push({ kind:'error', message: e.message || 'Error generando catálogo' }) }
    }}>Generar catálogo</button>
    <button className="btn" onClick={async () => {
      const ok = await headLatestCatalog(); if (!ok) { push({ kind:'error', message:'No hay catálogo disponible' }); return }
  window.open(base + '/catalogs/latest','_blank'); push({ kind:'info', message:'Abriendo catálogo actual' })
    }}>Ver catálogo</button>
    <button className="btn" onClick={async () => {
      const ok = await headLatestCatalog(); if (!ok) { push({ kind:'error', message:'No hay catálogo disponible' }); return }
  window.location.href = base + '/catalogs/latest/download'; push({ kind:'info', message:'Descargando catálogo' })
    }}>Descargar catálogo</button>
  <button className="btn" disabled={!items.length} onClick={toggleSelectAllOnPage}>{selected.size === items.length && items.length > 0 ? 'Deseleccionar página' : 'Seleccionar página'}</button>
  <button className="btn-secondary" disabled={!selected.size} onClick={clearSelection}>Limpiar selección</button>
  <button className="btn" disabled={!selected.size} onClick={() => setShowDeleteConfirm(true)}>Borrar seleccionados</button>
  <button className="btn" onClick={() => setShowHistory(true)}>Histórico catálogos</button>
    <button className="btn-dark" onClick={() => {
      const params = new URLSearchParams()
      if (q) params.set('q', q)
      if (supplierId) params.set('supplier_id', supplierId)
      if (categoryId) params.set('category_id', categoryId)
      params.set('stock', tab === 'gt' ? 'gt:0' : 'eq:0')
      // mantener orden por defecto del listado
      params.set('sort_by', 'updated_at')
      params.set('order', 'desc')
  const url = base + `/stock/export.xlsx?${params.toString()}`
  window.location.href = url
    }}>Descargar XLS</button>
    <button className="btn" onClick={() => {
      const params = new URLSearchParams()
      if (q) params.set('q', q)
      if (supplierId) params.set('supplier_id', supplierId)
      if (categoryId) params.set('category_id', categoryId)
      params.set('stock', tab === 'gt' ? 'gt:0' : 'eq:0')
      params.set('sort_by', 'updated_at')
      params.set('order', 'desc')
      const url = base + `/stock/export.csv?${params.toString()}`
      window.location.href = url
    }}>Descargar CSV</button>
    <button className="btn" onClick={() => {
      const params = new URLSearchParams()
      if (q) params.set('q', q)
      if (supplierId) params.set('supplier_id', supplierId)
      if (categoryId) params.set('category_id', categoryId)
      params.set('stock', tab === 'gt' ? 'gt:0' : 'eq:0')
      params.set('sort_by', 'updated_at')
      params.set('order', 'desc')
      const url = base + `/stock/export.pdf?${params.toString()}`
      // Abrir en nueva pestaña: el navegador puede previsualizar el PDF o descargar según configuración
      window.open(url, '_blank')
    }}>Exportar PDF</button>
    {canEdit && (
      <button className="btn" disabled={filling} onClick={async () => {
        setFilling(true)
        try {
          // Llamado directo al endpoint bulk
          const headers: Record<string, string> = {}
          {
            const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
            if (m) headers['X-CSRF-Token'] = decodeURIComponent(m[1])
          }
          const res = await fetch('/products-ex/supplier-items/fill-missing-sale', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json', ...headers },
            body: JSON.stringify({ supplier_id: supplierId ? Number(supplierId) : null }),
          })
          if (!res.ok) throw new Error(`HTTP ${res.status}`)
          const data = await res.json()
          push({ kind: 'success', message: `Precios de venta completados: ${data.updated}` })
          // Refrescar lista
          setPage(1); setItems([])
        } catch (e: any) {
          push({ kind: 'error', message: e?.message || 'No se pudo completar precios de venta' })
        } finally {
          setFilling(false)
        }
      }}>Completar ventas faltantes</button>
    )}
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
        <SupplierAutocomplete
          className="input"
          value={supplierSel}
          onChange={(item) => { setSupplierSel(item); setSupplierId(item ? String(item.id) : ''); resetAndSearch() }}
          placeholder="Proveedor"
        />
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
    <th></th>
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
            <tr key={it.product_id} className={selected.has(it.product_id) ? 'row-selected' : ''}>
      <td className="text-center">
        <input type="checkbox" checked={selected.has(it.product_id)} onChange={() => toggleSelect(it.product_id)} />
      </td>
      <td style={{ textAlign: 'left' }}>
        <a className="truncate product-title" href={`/productos/${it.product_id}`}>{it.name}</a>
      </td>
      <td style={{ textAlign: 'left' }}>{it.supplier.name}</td>
      <td className="text-center">
        {canEdit && it.canonical_product_id ? (
          editSaleId === it.canonical_product_id ? (
            <span>
              <input
                className="input"
                style={{ width: 100 }}
                value={saleVal}
                onChange={(e) => setSaleVal(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') saveSalePrice(it.canonical_product_id!); if (e.key === 'Escape') setEditSaleId(null) }}
                onBlur={() => saveSalePrice(it.canonical_product_id!)}
              />
            </span>
          ) : (
            <span>
              {(() => {
                const eff = (it.canonical_sale_price ?? (it as any).precio_venta) as number | null
                return eff != null ? `$ ${Number(eff).toFixed(2)}` : '-'
              })()}
              <button
                className="btn-secondary"
                style={{ marginLeft: 6 }}
                onClick={() => {
                  setEditSaleId(it.canonical_product_id!)
                  const eff = (it.canonical_sale_price ?? (it as any).precio_venta) as number | null
                  setSaleVal(eff != null ? String(eff) : '')
                }}
              >✎</button>
            </span>
          )
        ) : canEdit && (it as any).supplier_item_id ? (
          editSupplierSaleId === (it as any).supplier_item_id ? (
            <span>
              <input
                className="input"
                style={{ width: 100 }}
                value={supplierSaleVal}
                onChange={(e) => setSupplierSaleVal(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') saveSupplierSalePrice((it as any).supplier_item_id); if (e.key === 'Escape') setEditSupplierSaleId(null) }}
                onBlur={() => saveSupplierSalePrice((it as any).supplier_item_id)}
              />
            </span>
          ) : (
            <span>
              {(it as any).precio_venta != null ? `$ ${((it as any).precio_venta as number).toFixed(2)}` : '-'}
              <button className="btn-secondary" style={{ marginLeft: 6 }} onClick={() => { setEditSupplierSaleId((it as any).supplier_item_id); setSupplierSaleVal(String((it as any).precio_venta ?? '')) }}>✎</button>
            </span>
          )
        ) : (
          <span>{(() => {
            const eff = (it.canonical_sale_price ?? (it as any).precio_venta) as number | null
            return eff != null ? `$ ${Number(eff).toFixed(2)}` : ''
          })()}</span>
        )}
      </td>
      <td className="text-center">
        {canEdit && (it as any).supplier_item_id ? (
          editBuyId === (it as any).supplier_item_id ? (
            <span>
              <input
                className="input"
                style={{ width: 100 }}
                value={buyVal}
                onChange={(e) => setBuyVal(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') saveBuyPrice((it as any).supplier_item_id); if (e.key === 'Escape') setEditBuyId(null) }}
                onBlur={() => saveBuyPrice((it as any).supplier_item_id)}
              />
            </span>
          ) : (
            <span>
              {it.precio_compra != null ? `$ ${(it.precio_compra as number).toFixed(2)}` : '-'}
              <button className="btn-secondary" style={{ marginLeft: 6 }} onClick={() => { setEditBuyId((it as any).supplier_item_id); setBuyVal(String(it.precio_compra ?? '')) }}>✎</button>
            </span>
          )
        ) : (
          <span>{it.precio_compra ?? ''}</span>
        )}
      </td>
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
      <CatalogHistoryModal open={showHistory} onClose={() => setShowHistory(false)} />
      {showDeleteConfirm && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: 420 }}>
            <h3 style={{ marginTop: 0 }}>Confirmar borrado</h3>
            <p style={{ fontSize: 14 }}>
              Vas a borrar <strong>{selected.size}</strong> producto(s). Esta acción es permanente y eliminará también datos dependientes
              (imágenes, equivalencias, etc.) según las reglas del backend.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
              <button className="btn" disabled={deleting} onClick={() => setShowDeleteConfirm(false)}>Cancelar</button>
              <button className="btn-dark" disabled={deleting} onClick={async () => {
                if (!selected.size) return
                setDeleting(true)
                try {
                  const ids = Array.from(selected)
                  // Pre-chequeo: aviso si hay seleccionados con stock > 0
                  try {
                    const selSet = new Set(ids)
                    const withStock = items.filter(it => selSet.has(it.product_id) && (it.stock ?? 0) > 0)
                    if (withStock.length > 0) {
                      const showCount = Math.min(5, withStock.length)
                      const sample = withStock.slice(0, showCount).map(it => String(it.product_id)).join(', ')
                      push({ kind:'info', message: `Seleccionaste ${withStock.length} con stock > 0${withStock.length ? ` (ej: ${sample}${withStock.length > showCount ? '…' : ''})` : ''}. El backend bloqueará esos borrados.` })
                    }
                  } catch {}
                  const r = await deleteProducts(ids)
                  const parts: string[] = []
                  parts.push(`Borrados ${r.deleted.length} / ${r.requested.length}`)
                  if (r.blocked_stock.length) {
                    const showCount = Math.min(5, r.blocked_stock.length)
                    const sample = r.blocked_stock.slice(0, showCount).join(', ')
                    parts.push(`con stock: ${r.blocked_stock.length}${r.blocked_stock.length ? ` (ej: ${sample}${r.blocked_stock.length > showCount ? '…' : ''})` : ''}`)
                  }
                  if (r.blocked_refs.length) {
                    const showCount = Math.min(5, r.blocked_refs.length)
                    const sample = r.blocked_refs.slice(0, showCount).join(', ')
                    parts.push(`en compras: ${r.blocked_refs.length}${r.blocked_refs.length ? ` (ej: ${sample}${r.blocked_refs.length > showCount ? '…' : ''})` : ''}`)
                  }
                  push({ kind: 'success', message: parts.join(' | ') })
                  if ((r.blocked_stock?.length || 0) + (r.blocked_refs?.length || 0)) {
                    push({ kind:'info', message:'Sugerencia: usá el tab "Sin stock" para eliminar fácilmente los que quedaron bloqueados por stock.' })
                  }
                  // Remover solo los realmente eliminados
                  const deletedSet = new Set(r.deleted)
                  setItems(prev => prev.filter(it => !deletedSet.has(it.product_id)))
                  clearSelection()
                  setShowDeleteConfirm(false)
                } catch (e: any) {
                  push({ kind: 'error', message: e?.message || e?.response?.data?.detail || 'No se pudieron eliminar' })
                } finally {
                  setDeleting(false)
                }
              }}>Confirmar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
