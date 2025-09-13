// NG-HEADER: Nombre de archivo: ProductCreateModal.tsx
// NG-HEADER: Ubicación: frontend/src/components/ProductCreateModal.tsx
// NG-HEADER: Descripción: Modal para creación manual de productos
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useState } from 'react'
import { createProduct } from '../services/products'
import { listCategories, Category } from '../services/categories'
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
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)

  async function ensureCats() {
    if (loaded) return
    try {
      const cats = await listCategories()
      setCategories(cats)
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
    setLoading(true)
    try {
      const created = await createProduct({
        title: title.trim(),
        category_id: categoryId ? Number(categoryId) : undefined,
        initial_stock: stockNum,
      })
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
          <label className="label" style={{ marginTop: 12 }}>Categoría (opcional)</label>
          <select
            className="select w-full"
            value={categoryId}
            onFocus={ensureCats}
            onChange={(e) => setCategoryId(e.target.value)}
          >
            <option value="">Sin categoría</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <label className="label" style={{ marginTop: 12 }}>Stock inicial</label>
          <input
            className="input"
            type="number"
            min={0}
            value={initialStock}
            onChange={(e) => setInitialStock(e.target.value)}
          />
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 20 }}>
            <button type="button" className="btn" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn-dark" disabled={loading}>{loading ? 'Creando...' : 'Crear'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}