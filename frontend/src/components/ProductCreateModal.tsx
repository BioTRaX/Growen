// NG-HEADER: Nombre de archivo: ProductCreateModal.tsx
// NG-HEADER: Ubicación: frontend/src/components/ProductCreateModal.tsx
// NG-HEADER: Descripción: Modal para creación manual de productos
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useState } from 'react'
import { createProduct } from '../services/products'
import { listSuppliers, createSupplierItem } from '../services/suppliers'
import { listCategories, createCategory, Category } from '../services/categories'
import { showToast } from './Toast'

interface Props {
  onCreated: (p: { id: number; title: string }) => void
  onClose: () => void
}

export default function ProductCreateModal({ onCreated, onClose }: Props) {
  const [title, setTitle] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [initialStock, setInitialStock] = useState('0')
  const [categories, setCategories] = useState<Category[]>([])
  const [suppliers, setSuppliers] = useState<{ id: number; name: string }[]>([])
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [showCreateCat, setShowCreateCat] = useState(false)
  const [newCatName, setNewCatName] = useState('')
  const [newCatParentId, setNewCatParentId] = useState<string>('')
  const [supplierId, setSupplierId] = useState('')
  const [supplierSku, setSupplierSku] = useState('')
  const [purchasePrice, setPurchasePrice] = useState('')
  const [salePrice, setSalePrice] = useState('')

  async function ensureCats() {
    if (loaded) return
    try {
      const cats = await listCategories()
      setCategories(cats)
      // Cargar proveedores en paralelo
      listSuppliers().then((s) => setSuppliers(s.map(x => ({ id: x.id, name: x.name })))).catch(() => {})
      setLoaded(true)
    } catch {}
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    const stockNum = Number(initialStock)
    if (isNaN(stockNum) || stockNum < 0) {
      showToast('error', 'Stock inicial inválido')
      return
    }
    // Validaciones mínimas
    if (!supplierId) {
      showToast('error', 'Seleccioná un proveedor')
      return
    }
    const pp = Number(purchasePrice.replace(/,/g, '.'))
    const sp = Number(salePrice.replace(/,/g, '.'))
    if (!isFinite(pp) || pp <= 0) { showToast('error', 'Precio de compra inválido'); return }
    if (!isFinite(sp) || sp <= 0) { showToast('error', 'Precio de venta inválido'); return }
    setLoading(true)
    try {
      const payload: any = {
        title: title.trim(),
        initial_stock: stockNum,
      }
      if (showCreateCat && newCatName.trim()) {
        payload.new_category_name = newCatName.trim()
        if (newCatParentId) {
          payload.new_category_parent_id = Number(newCatParentId)
        }
      } else if (categoryId) {
        payload.category_id = Number(categoryId)
      }

      // Crear producto base (endpoint completo que mantiene auditoría y categorías inline)
      const created = await createProduct(payload)
      // Vincular proveedor + registrar precios creando el SupplierItem
      try {
        await createSupplierItem(Number(supplierId), {
          supplier_product_id: supplierSku.trim() || created.sku_root,
          title: created.title,
          product_id: created.id,
          purchase_price: pp,
          sale_price: sp,
        })
      } catch (err: any) {
        // Si ya existe el ítem, seguimos (idempotencia)
        const msg = String(err?.message || '')
        if (!/duplicado|existe/i.test(msg)) throw err
      }
      showToast('success', 'Producto creado')
      onCreated({ id: created.id, title: created.title })
      onClose()
    } catch (e: any) {
      showToast('error', e.message || 'No se pudo crear el producto')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal" style={{ width: 480, maxWidth: '90%' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ flex: 1, margin: 0 }}>Nuevo producto</h3>
          <button className="btn" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={submit}>
          <label className="label">Nombre</label>
          <input
            className="input w-full"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            placeholder="Nombre del producto"
            autoFocus
          />
          <label className="label" style={{ marginTop: 12 }}>Proveedor</label>
          <select
            className="select w-full"
            value={supplierId}
            onFocus={ensureCats}
            onChange={(e) => setSupplierId(e.target.value)}
            required
          >
            <option value="">Seleccioná proveedor</option>
            {suppliers.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 12 }}>
            <div>
              <label className="label">SKU del proveedor (opcional)</label>
              <input className="input w-full" value={supplierSku} onChange={e => setSupplierSku(e.target.value)} placeholder="Si se omite, se usa el SKU interno" />
            </div>
            <div>
              <label className="label">Stock inicial</label>
              <input
                className="input"
                type="number"
                min={0}
                value={initialStock}
                onChange={(e) => setInitialStock(e.target.value)}
              />
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 12 }}>
            <div>
              <label className="label">Precio de compra</label>
              <input className="input w-full" inputMode="decimal" value={purchasePrice} onChange={e => setPurchasePrice(e.target.value)} placeholder="0,00" required />
            </div>
            <div>
              <label className="label">Precio de venta</label>
              <input className="input w-full" inputMode="decimal" value={salePrice} onChange={e => setSalePrice(e.target.value)} placeholder="0,00" required />
            </div>
          </div>
          <label className="label" style={{ marginTop: 12 }}>Categoría (opcional)</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <select
              className="select w-full"
              value={categoryId}
              onFocus={ensureCats}
              onChange={(e) => { setCategoryId(e.target.value); setShowCreateCat(false); }}
              disabled={showCreateCat}
            >
              <option value="">Sin categoría</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.path}</option>
              ))}
            </select>
            <button type="button" className="btn" onClick={() => { ensureCats(); setShowCreateCat(v => !v); }}>
              {showCreateCat ? 'Cancelar' : 'Nueva'}
            </button>
          </div>

          {showCreateCat && (
            <div style={{ border: '1px solid var(--border-color)', borderRadius: 4, padding: 12, marginTop: 12 }}>
              <h4 style={{marginTop: 0, fontSize: 14}}>Nueva Categoría</h4>
              <label className="label">Nombre</label>
              <input
                className="input w-full"
                value={newCatName}
                onChange={(e) => setNewCatName(e.target.value)}
                placeholder="Ej: Fertilizantes"
              />
              <label className="label" style={{ marginTop: 8 }}>Padre (opcional)</label>
              <select
                className="select w-full"
                value={newCatParentId}
                onChange={(e) => setNewCatParentId(e.target.value)}
              >
                <option value="">(Raíz)</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.path}</option>
                ))}
              </select>
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 20 }}>
            <button type="button" className="btn" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn-dark" disabled={loading}>{loading ? 'Creando...' : 'Crear'}</button>
          </div>
        </form>
        {/* The submodal is no longer needed as the form is now inline */}
      </div>
    </div>
  )
}