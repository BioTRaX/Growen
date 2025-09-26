// NG-HEADER: Nombre de archivo: CanonicalForm.tsx
// NG-HEADER: Ubicación: frontend/src/components/CanonicalForm.tsx
// NG-HEADER: Descripción: Formulario React para editar productos canónicos.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useMemo, useState } from 'react'
import {
  createCanonicalProduct,
  getCanonicalProduct,
  updateCanonicalProduct,
  CanonicalProduct,
} from '../services/canonical'
import { listCategories, createCategory, Category } from '../services/categories'
import { getNextSeq } from '../services/canonical'

interface Props {
  canonicalId?: number
  onClose: () => void
  onSaved?: (cp: CanonicalProduct) => void
  initialName?: string
}

export default function CanonicalForm({ canonicalId, onClose, onSaved, initialName }: Props) {
  const [name, setName] = useState('')
  const [brand, setBrand] = useState('')
  const [saving, setSaving] = useState(false)
  const [skuCustom, setSkuCustom] = useState('')
  const [categoryId, setCategoryId] = useState<number | ''>('')
  const [subcategoryId, setSubcategoryId] = useState<number | ''>('')
  const [categories, setCategories] = useState<Category[]>([])
  const [showNewCat, setShowNewCat] = useState(false)
  const [newCatName, setNewCatName] = useState('')
  const [showNewSubcat, setShowNewSubcat] = useState(false)
  const [newSubcatName, setNewSubcatName] = useState('')

  useEffect(() => {
    listCategories().then(setCategories).catch(() => {})
    if (canonicalId) {
      getCanonicalProduct(canonicalId)
        .then((cp) => {
          setName(cp.name)
          setBrand(cp.brand || '')
          setSkuCustom(cp.sku_custom || '')
          setCategoryId((cp.category_id ?? undefined) ? (cp.category_id as number) : '')
          setSubcategoryId((cp.subcategory_id ?? undefined) ? (cp.subcategory_id as number) : '')
        })
        .catch(() => {})
    } else if (initialName) {
      setName(initialName)
    }
  }, [canonicalId])

  async function save() {
    try {
      setSaving(true)
      let cp: CanonicalProduct
      if (canonicalId) {
        cp = await updateCanonicalProduct(canonicalId, {
          name,
          brand: brand || null,
          sku_custom: skuCustom.trim() || null,
          category_id: typeof categoryId === 'number' ? categoryId : null,
          subcategory_id: typeof subcategoryId === 'number' ? subcategoryId : null,
        })
      } else {
        cp = await createCanonicalProduct({
          name,
          brand: brand || null,
          sku_custom: skuCustom.trim() || null,
          category_id: typeof categoryId === 'number' ? categoryId : null,
          subcategory_id: typeof subcategoryId === 'number' ? subcategoryId : null,
        })
      }
      onSaved?.(cp)
      onClose()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0,0,0,0.3)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div className="panel p-4" style={{ width: 520 }}>
        <h3>{canonicalId ? 'Editar canónico' : 'Nuevo canónico'}</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <input
            className="input"
            placeholder="Nombre"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            className="input"
            placeholder="Marca"
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <div style={{ flex: 1 }}>
              <label className="text-sm" style={{ display: 'block', marginBottom: 4 }}>SKU propio</label>
              <input className="input w-full" placeholder="Ej: FER_0023_LIQ" value={skuCustom} onChange={(e) => setSkuCustom(e.target.value.toUpperCase())} />
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button
                className="btn"
                onClick={async () => {
                  const catId = typeof categoryId === 'number' ? categoryId : null
                  try {
                    const seq = await getNextSeq(catId)
                    // Preview rule: take first 3 of category/subcategory names; we keep it simple here
                    const catName = categories.find(c => c.id === catId)?.name || ''
                    const subName = categories.find(c => c.id === (typeof subcategoryId === 'number' ? subcategoryId : -1))?.name || ''
                    const seg = (s: string) => s.normalize('NFD').replace(/[^A-Za-z]/g, '').toUpperCase().slice(0,3).padEnd(3,'X')
                    const preview = `${seg(catName)}_${String(seq).padStart(4,'0')}_${seg(subName || 'GEN')}`
                    setSkuCustom(preview)
                  } catch {}
                }}
                title="Autogenerar con vista previa"
                style={{ height: 40 }}
              >Auto</button>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <div style={{ flex: 1 }}>
              <label className="text-sm" style={{ display: 'block', marginBottom: 4 }}>Categoría</label>
              <div style={{ display: 'flex', gap: 6 }}>
                <select className="select w-full" value={categoryId === '' ? '' : String(categoryId)} onChange={(e) => { const v = e.target.value ? Number(e.target.value) : ''; setCategoryId(v); setSubcategoryId('') }}>
                  <option value="">Sin categoría</option>
                  {categories.filter(c => !c.parent_id).map(c => (<option key={c.id} value={c.id}>{c.name}</option>))}
                </select>
                <button className="btn" onClick={() => setShowNewCat(true)}>Nueva</button>
              </div>
            </div>
            <div style={{ flex: 1 }}>
              <label className="text-sm" style={{ display: 'block', marginBottom: 4 }}>Subcategoría</label>
              <div style={{ display: 'flex', gap: 6 }}>
                <select className="select w-full" value={subcategoryId === '' ? '' : String(subcategoryId)} onChange={(e) => setSubcategoryId(e.target.value ? Number(e.target.value) : '')}>
                  <option value="">(ninguna)</option>
                  {categories.map(c => (<option key={c.id} value={c.id}>{c.name}{c.parent_id ? '' : ''}</option>))}
                </select>
                <button className="btn" onClick={() => setShowNewSubcat(true)}>Nueva</button>
              </div>
            </div>
          </div>
        </div>
        <div style={{ marginTop: 12, textAlign: 'right' }}>
          <button onClick={onClose} style={{ marginRight: 8 }}>
            Cancelar
          </button>
          <button onClick={save} disabled={saving || !name}>
            {saving ? 'Guardando...' : 'Guardar'}
          </button>
        </div>
        {showNewCat && (
          <div className="modal-backdrop">
            <div className="modal" style={{ maxWidth: 420 }}>
              <h3 style={{ marginTop: 0 }}>Nueva categoría</h3>
              <input className="input w-full" placeholder="Nombre" value={newCatName} onChange={(e) => setNewCatName(e.target.value)} />
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
                <button className="btn" onClick={() => setShowNewCat(false)}>Cancelar</button>
                <button className="btn-dark" onClick={async () => {
                  const name = newCatName.trim(); if (!name) return
                  try { await createCategory(name, null); const list = await listCategories(); setCategories(list); setShowNewCat(false); setNewCatName('') } catch {}
                }}>Crear</button>
              </div>
            </div>
          </div>
        )}
        {showNewSubcat && (
          <div className="modal-backdrop">
            <div className="modal" style={{ maxWidth: 460 }}>
              <h3 style={{ marginTop: 0 }}>Nueva subcategoría</h3>
              <label className="text-sm">Padre (opcional)</label>
              <select className="select w-full" value={categoryId === '' ? '' : String(categoryId)} onChange={(e) => setCategoryId(e.target.value ? Number(e.target.value) : '')}>
                <option value="">(ninguno)</option>
                {categories.filter(c => !c.parent_id).map(c => (<option key={c.id} value={c.id}>{c.name}</option>))}
              </select>
              <label className="text-sm" style={{ marginTop: 8 }}>Nombre</label>
              <input className="input w-full" placeholder="Nombre" value={newSubcatName} onChange={(e) => setNewSubcatName(e.target.value)} />
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
                <button className="btn" onClick={() => setShowNewSubcat(false)}>Cancelar</button>
                <button className="btn-dark" onClick={async () => {
                  const name = newSubcatName.trim(); const parent = typeof categoryId === 'number' ? categoryId : null
                  if (!name) return
                  try { await createCategory(name, parent); const list = await listCategories(); setCategories(list); setShowNewSubcat(false); setNewSubcatName('') } catch {}
                }}>Crear</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
