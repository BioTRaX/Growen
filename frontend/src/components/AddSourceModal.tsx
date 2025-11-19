// NG-HEADER: Nombre de archivo: AddSourceModal.tsx
// NG-HEADER: Ubicación: frontend/src/components/AddSourceModal.tsx
// NG-HEADER: Descripción: Modal para agregar nueva fuente de precio de mercado
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { useState } from 'react'
import { useToast } from './ToastProvider'
import { addProductSource, validateSourceUrl, type AddSourcePayload } from '../services/market'

interface AddSourceModalProps {
  productId: number
  open: boolean
  onClose: () => void
  onSuccess: () => void
}

export default function AddSourceModal({ productId, open, onClose, onSuccess }: AddSourceModalProps) {
  const { push } = useToast()
  
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [isMandatory, setIsMandatory] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [errors, setErrors] = useState<{ name?: string; url?: string }>({})

  function validate(): boolean {
    const newErrors: { name?: string; url?: string } = {}
    
    // Validar nombre
    if (!name.trim()) {
      newErrors.name = 'El nombre de la fuente es obligatorio'
    } else if (name.trim().length < 3) {
      newErrors.name = 'El nombre debe tener al menos 3 caracteres'
    } else if (name.trim().length > 200) {
      newErrors.name = 'El nombre no puede exceder 200 caracteres'
    }
    
    // Validar URL
    if (!url.trim()) {
      newErrors.url = 'La URL es obligatoria'
    } else {
      const urlValidation = validateSourceUrl(url.trim())
      if (!urlValidation.valid) {
        newErrors.url = urlValidation.error
      }
    }
    
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    
    if (!validate()) return
    
    setSubmitting(true)
    try {
      const payload: AddSourcePayload = {
        name: name.trim(),
        url: url.trim(),
        is_mandatory: isMandatory,
      }
      
      await addProductSource(productId, payload)
      
      // Resetear formulario
      setName('')
      setUrl('')
      setIsMandatory(false)
      setErrors({})
      
      onSuccess()
    } catch (error: any) {
      push({
        kind: 'error',
        message: error?.message || 'Error agregando fuente',
      })
    } finally {
      setSubmitting(false)
    }
  }

  function handleClose() {
    if (submitting) return
    setName('')
    setUrl('')
    setIsMandatory(false)
    setErrors({})
    onClose()
  }

  if (!open) return null

  return (
    <div className="modal-backdrop" onClick={handleClose} style={{ zIndex: 1001 }}>
      <div 
        className="modal" 
        style={{ maxWidth: 500 }} 
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ marginTop: 0, marginBottom: 16 }}>Agregar Nueva Fuente</h3>
        
        <form onSubmit={handleSubmit}>
          {/* Nombre de la fuente */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 14, fontWeight: 500 }}>
              Nombre de la fuente *
            </label>
            <input
              type="text"
              className="input w-full"
              placeholder="Ej: MercadoLibre, SantaPlanta, Tienda Online..."
              value={name}
              onChange={(e) => {
                setName(e.target.value)
                if (errors.name) setErrors({ ...errors, name: undefined })
              }}
              disabled={submitting}
              maxLength={200}
            />
            {errors.name && (
              <div style={{ color: '#ef4444', fontSize: 12, marginTop: 4 }}>
                {errors.name}
              </div>
            )}
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
              Nombre identificativo de la tienda o sitio web
            </div>
          </div>

          {/* URL de la fuente */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 14, fontWeight: 500 }}>
              URL del producto *
            </label>
            <input
              type="url"
              className="input w-full"
              placeholder="https://www.ejemplo.com/producto"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value)
                if (errors.url) setErrors({ ...errors, url: undefined })
              }}
              disabled={submitting}
            />
            {errors.url && (
              <div style={{ color: '#ef4444', fontSize: 12, marginTop: 4 }}>
                {errors.url}
              </div>
            )}
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
              URL completa del producto en el sitio de la fuente
            </div>
          </div>

          {/* Tipo de fuente */}
          <div style={{ marginBottom: 24 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={isMandatory}
                onChange={(e) => setIsMandatory(e.target.checked)}
                disabled={submitting}
                style={{ cursor: 'pointer' }}
              />
              <span style={{ fontSize: 14 }}>Marcar como fuente obligatoria</span>
            </label>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4, marginLeft: 24 }}>
              Las fuentes obligatorias se actualizan prioritariamente en cada scraping
            </div>
          </div>

          {/* Ejemplos de fuentes comunes */}
          <div 
            style={{ 
              padding: 12, 
              background: 'var(--panel-bg)', 
              borderRadius: 8, 
              marginBottom: 24,
              fontSize: 12,
            }}
          >
            <div style={{ fontWeight: 500, marginBottom: 8 }}>💡 Ejemplos de fuentes comunes:</div>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              <li>MercadoLibre Argentina</li>
              <li>SantaPlanta</li>
              <li>Fabricante directo</li>
              <li>Competidores locales</li>
            </ul>
          </div>

          {/* Botones */}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button 
              type="button"
              className="btn" 
              onClick={handleClose}
              disabled={submitting}
            >
              Cancelar
            </button>
            <button 
              type="submit"
              className="btn-primary" 
              disabled={submitting}
            >
              {submitting ? 'Agregando...' : 'Agregar Fuente'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
