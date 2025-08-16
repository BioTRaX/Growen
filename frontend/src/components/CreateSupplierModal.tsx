import { useEffect, useState } from 'react'
import { createSupplier, Supplier } from '../services/suppliers'
import { showToast } from './Toast'

interface Props {
  open: boolean
  onClose: () => void
  onCreated: (s: Supplier) => void
}

function slugify(text: string) {
  return text
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '')
    .replace(/-+/g, '-')
}

export default function CreateSupplierModal({ open, onClose, onCreated }: Props) {
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    setSlug(slugify(name))
  }, [name])

  async function submit() {
    const n = name.trim()
    const re = /^[a-z0-9-]+$/
    if (!n || !re.test(slug)) {
      setError('Datos inválidos')
      return
    }
    try {
      const s = await createSupplier({ name: n, slug })
      showToast('success', 'Proveedor creado')
      onCreated(s)
    } catch (e: any) {
      if (e.message === 'slug existente') setError('El slug ya existe')
      else setError(e.message)
    }
  }

  if (!open) return null

  return (
    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: '#fff', padding: 20, borderRadius: 8, width: 300 }}>
        <h4>Nuevo proveedor</h4>
        {error && <div style={{ color: 'red' }}>{error}</div>}
        <div style={{ margin: '8px 0' }}>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nombre" style={{ width: '100%', padding: 8 }} />
        </div>
        <div style={{ margin: '8px 0' }}>
          <input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="Slug" style={{ width: '100%', padding: 8 }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
          <button onClick={onClose}>Cancelar</button>
          <button onClick={submit}>Crear</button>
        </div>
      </div>
    </div>
  )
}
